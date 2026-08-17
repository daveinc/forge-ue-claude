"""Which provider earns a bounded work order, and on what evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_core import ERROR_REASON, EXIT_USAGE, RESIDENT_PROVIDER, fail, load_json, plugin_root, project_root
from forge_hosts import active_profile
from forge_mcp import mcp_capability_contracts


ISOLATION_STRENGTH = ("read-only", "git-worktree", "lfs-lock", "project-exclusive")


def resolve_tool_access(contracts: dict[str, Any], required_capabilities: set[str]) -> list[dict[str, Any]]:
    """What each required capability resolves to right now, and what holding it would take.

    A capability no route serves is not an error: the resident host or an engine
    prerequisite answers it. A capability a route serves but cannot reach today is
    the case the declared fallback exists for, and it must be reported rather than
    dispatched into.
    """
    resolved: list[dict[str, Any]] = []
    for name in sorted(required_capabilities):
        contract = contracts.get(name)
        if contract is None:
            resolved.append(
                {
                    "capability": name,
                    "routed": False,
                    "bound": True,
                    "provider": RESIDENT_PROVIDER,
                    "kind": "resident",
                    "lane": None,
                    "lease": None,
                    "isolation_mode": None,
                    "fallbacks": [],
                    "detail": "no typed route serves this capability; the resident host or an engine prerequisite answers it",
                }
            )
            continue
        bound = str(contract.get("status", "")).startswith("AVAILABLE")
        resolved.append(
            {
                "capability": name,
                "routed": True,
                "bound": bound,
                "provider": contract.get("provider"),
                "kind": contract.get("kind"),
                "status": contract.get("status"),
                "lane": contract.get("lane"),
                "lease": contract.get("lease"),
                "isolation_mode": contract.get("isolation_mode"),
                "fallbacks": contract.get("fallbacks", []),
                "detail": contract.get("detection_note"),
            }
        )
    return resolved


def strictest_isolation(modes: set[str]) -> str | None:
    ranked = [mode for mode in ISOLATION_STRENGTH if mode in modes]
    return ranked[-1] if ranked else None


def route_conflicts(packet: dict[str, Any], decision: dict[str, Any]) -> list[str]:
    """Every way a packet contradicts the routing decision that authorised it.

    Routing resolves which lanes the work needs and how strongly it must be
    isolated. A packet that holds less than that would run outside the protection
    routing decided it required, which no lease can detect after the fact.
    """
    conflicts: list[str] = []
    order = str(packet.get("work_order", ""))
    canonical = str(decision.get("canonical_work_order", ""))
    if canonical and order and order != canonical:
        conflicts.append(f"packet is work order {order!r}; the decision authorises {canonical!r}")
    if decision.get("tool_access_degraded"):
        degraded = ", ".join(str(item.get("capability")) for item in decision.get("degraded_capabilities", []))
        conflicts.append(
            f"routing marked tool access degraded for {degraded}; take the declared fallback rather than the lane"
        )
    routed = {str(item) for item in decision.get("leases", []) if item}
    declared = {str(item) for item in packet.get("leases", []) if item}
    for missing in sorted(routed - declared):
        conflicts.append(f"routing requires lease {missing!r}, which the packet does not declare")
    required_mode = decision.get("isolation_mode")
    packet_mode = str((packet.get("isolation") or {}).get("mode", ""))
    if required_mode and packet_mode:
        if ISOLATION_STRENGTH.index(required_mode) > ISOLATION_STRENGTH.index(packet_mode):
            conflicts.append(
                f"routing requires {required_mode!r} isolation; the packet declares the weaker {packet_mode!r}"
            )
    return conflicts


def route_work(project_value: str, request_value: str, host_override: str | None = None) -> dict[str, Any]:
    root, _ = project_root(project_value)
    profile = active_profile(root, host_override)
    request_path = Path(request_value).expanduser().resolve()
    request = load_json(request_path)
    required = {"work_order", "task_class", "complexity", "bounded", "required_capabilities", "required_lanes", "mutation_risk"}
    missing = sorted(required - set(request))
    if missing:
        raise fail("Route request missing: " + ", ".join(missing), reason=ERROR_REASON["CONTRACT_INVALID"], code=EXIT_USAGE)

    packet_registry_path = root / ".forge" / "state" / "packet-registry.json"
    if not packet_registry_path.is_file():
        raise fail("Canonical packet registry is missing; apply the Forge overlay before routing", reason=ERROR_REASON["OVERLAY_MISSING"])
    packet_registry = load_json(packet_registry_path)
    packets = {str(item.get("id")): item for item in packet_registry.get("packets", [])}
    aliases = {str(item.get("alias")): str(item.get("canonical")) for item in packet_registry.get("aliases", [])}
    requested_order = str(request["work_order"])
    canonical_order = aliases.get(requested_order, requested_order)
    if canonical_order not in packets:
        raise fail(f"Unregistered work_order {requested_order!r}; register the canonical packet or an explicit alias before routing", reason=ERROR_REASON["CONTRACT_INVALID"])

    policy = load_json(plugin_root() / "dependencies" / "route-policy.json")
    offload = policy["offload_policy"]
    keep_on_resident = set(offload["keep_on_resident_by_default"])
    hard_resident = (
        not bool(request["bounded"])
        or request["task_class"] in keep_on_resident
        or request["complexity"] == "critical"
        or request["mutation_risk"] in {"external-write", "destructive"}
    )

    detected_path = root / ".forge" / "capabilities" / "detected.json"
    qualification_path = root / ".forge" / "capabilities" / "qualifications.json"
    detected = load_json(detected_path) if detected_path.exists() else {"providers": []}
    qualifications = load_json(qualification_path) if qualification_path.exists() else {"evaluations": []}
    provider_status = {str(item.get("id")): item.get("status") for item in detected.get("providers", [])}

    contracts = {str(item["capability"]): item for item in mcp_capability_contracts(root, profile)}
    for item in contracts.values():
        provider_status[str(item.get("provider"))] = item.get("status")

    required_capabilities = set(request.get("required_capabilities", []))
    required_lanes = set(request.get("required_lanes", []))
    tool_access = resolve_tool_access(contracts, required_capabilities)
    unbound = [item for item in tool_access if item["routed"] and not item["bound"]]
    holding = [item for item in tool_access if item["routed"] and item["bound"]]
    lanes = sorted({item["lane"] for item in holding if item["lane"]})
    leases = sorted({item["lease"] for item in holding if item["lease"]})
    isolation_mode = strictest_isolation({item["isolation_mode"] for item in holding if item["isolation_mode"]})
    undeclared_lanes = sorted(set(lanes) - required_lanes)
    unserved_lanes = sorted(required_lanes - set(lanes))

    candidates = [
        {
            "provider": RESIDENT_PROVIDER,
            "host": profile["id"],
            "eligible": True,
            "score": 0.0,
            "reason": f"resident baseline ({profile.get('display_name', profile['id'])})",
        }
    ]
    resident_aliases = {RESIDENT_PROVIDER, profile["id"]}
    for evaluation in qualifications.get("evaluations", []):
        provider = str(evaluation.get("provider", ""))
        if not provider or provider in resident_aliases:
            continue
        reasons = []
        if evaluation.get("verdict") != "PASS":
            reasons.append("evaluation did not pass")
        evidence_host = evaluation.get("host")
        if evidence_host and evidence_host != profile["id"]:
            reasons.append(f"qualification recorded under host {evidence_host!r}; re-probe under {profile['id']!r}")
        if evaluation.get("task_class") != request["task_class"] or evaluation.get("complexity") != request["complexity"]:
            reasons.append("task or complexity scope mismatch")
        if not required_capabilities.issubset(set(evaluation.get("capabilities", []))):
            reasons.append("required capability missing")
        if not required_lanes.issubset(set(evaluation.get("lanes", []))):
            reasons.append("required lane missing")
        if provider_status.get(provider) not in {"AVAILABLE_VERIFIED", "AVAILABLE_UNVERIFIED"}:
            reasons.append("provider unavailable or absent from current detection")
        metrics = evaluation.get("metrics", {})
        score = sum(float(metrics.get(name, 0.0)) for name in policy["score"]["positive"])
        score -= sum(float(metrics.get(name, 0.0)) for name in policy["score"]["negative"])
        candidates.append(
            {
                "provider": provider,
                "host": evidence_host,
                "eligible": not reasons,
                "score": round(score, 6),
                "reason": "; ".join(reasons) if reasons else "exact qualification passed",
            }
        )

    eligible_optional = sorted(
        (item for item in candidates if item["provider"] != RESIDENT_PROVIDER and item["eligible"]),
        key=lambda item: (item["score"], item["provider"]),
        reverse=True,
    )
    if hard_resident:
        selected = RESIDENT_PROVIDER
        decision = "resident-required-by-policy"
    elif eligible_optional and eligible_optional[0]["score"] > 0:
        selected = eligible_optional[0]["provider"]
        decision = "qualified-optional-advantage"
    else:
        selected = RESIDENT_PROVIDER
        decision = "no-qualified-positive-advantage"
    return {
        "schema": "forge.route-decision/v1",
        "project": str(root.resolve()),
        "request": request,
        "canonical_work_order": canonical_order,
        "selected": selected,
        "resident_host": profile["id"],
        "decision": decision,
        "candidates": candidates,
        "fallback": RESIDENT_PROVIDER,
        "tool_access": tool_access,
        "lanes": lanes,
        "leases": leases,
        "isolation_mode": isolation_mode,
        "tool_access_degraded": bool(unbound),
        "degraded_capabilities": [
            {"capability": item["capability"], "status": item.get("status"), "take_fallback": item["fallbacks"]}
            for item in unbound
        ],
        "lane_warnings": (
            [f"route implies lane {lane!r}, which the request did not declare in required_lanes" for lane in undeclared_lanes]
            + [f"request declares lane {lane!r}, which no bound route serves" for lane in unserved_lanes]
        ),
        "requires_independent_verification": True,
    }
