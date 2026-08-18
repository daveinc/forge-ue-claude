"""Which provider earns a bounded work order, and on what evidence."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import forge_executor as executor
from forge_core import ERROR_REASON, EXIT_CONTRACT, EXIT_USAGE, RESIDENT_PROVIDER, fail, load_json, plugin_root, project_root, utc_now
from forge_hosts import active_profile
from forge_mcp import catalog_tool_names, mcp_capability_contracts


ISOLATION_STRENGTH = ("read-only", "git-worktree", "lfs-lock", "project-exclusive")


ROUTE_DECISIONS_SCHEMA = "forge.route-decisions/v1"


DEFAULT_FRESHNESS_MINUTES = 30


def route_policy() -> dict[str, Any]:
    return load_json(plugin_root() / "dependencies" / "route-policy.json")


def route_decisions_path(root: Path) -> Path:
    return root / ".forge" / "state" / "route-decisions.json"


def decision_freshness_minutes(policy: dict[str, Any] | None = None) -> int:
    settings = (policy or route_policy()).get("route_decision") or {}
    return int(settings.get("freshness_minutes", DEFAULT_FRESHNESS_MINUTES))


def read_route_decisions(root: Path) -> dict[str, Any]:
    """Read the decision ledger. Absent is empty, malformed is a refusal."""
    path = route_decisions_path(root)
    if not path.is_file():
        return {"schema": ROUTE_DECISIONS_SCHEMA, "decisions": [], "updated_at": None}
    document = load_json(path)
    if not isinstance(document.get("decisions"), list):
        raise fail(
            f"{path} does not carry a {ROUTE_DECISIONS_SCHEMA} decisions array",
            reason=ERROR_REASON["CONTRACT_INVALID"],
            code=EXIT_CONTRACT,
        )
    return document


def canonical_order(packet_registry: dict[str, Any], work_order: str) -> str:
    """The registered id behind a work order, resolving one alias hop."""
    aliases = {str(item.get("alias")): str(item.get("canonical")) for item in packet_registry.get("aliases", [])}
    return aliases.get(work_order, work_order)


def record_route_decision(root: Path, decision: dict[str, Any], owner: str | None = None) -> dict[str, Any]:
    """Write the decision under its canonical work order, replacing any earlier one."""
    path = route_decisions_path(root)
    order = str(decision.get("canonical_work_order", ""))
    entry = {
        "canonical_work_order": order,
        "recorded_at": utc_now(),
        "recorded_by": owner,
        "decision": decision,
    }
    with executor.StateMutex(root, state_path=path) as _mutex:
        document = read_route_decisions(root)
        document["schema"] = ROUTE_DECISIONS_SCHEMA
        document["decisions"] = [
            item for item in document["decisions"] if str(item.get("canonical_work_order")) != order
        ] + [entry]
        document["updated_at"] = entry["recorded_at"]
        executor.write_state_atomically(path, document)
    return entry


def resolve_route_decision(root: Path, work_order: str, freshness_minutes: int | None = None) -> dict[str, Any]:
    """The recorded decision authorising this work order, or the reason there is none.

    Acquisition reads the decision rather than being handed one, so an agent that
    skipped routing cannot acquire by omitting a flag, and a decision the
    environment has outlived cannot authorise a lane it no longer describes.
    """
    packet_registry_path = root / ".forge" / "state" / "packet-registry.json"
    registry = load_json(packet_registry_path) if packet_registry_path.is_file() else {}
    order = canonical_order(registry, work_order)
    document = read_route_decisions(root)
    entry = next(
        (item for item in document["decisions"] if str(item.get("canonical_work_order")) == order),
        None,
    )
    if entry is None:
        raise fail(
            f"No routing decision is recorded for work order {order!r}; run "
            f"`forge.py route --project {root} --request <request> --apply` before acquiring, or pass "
            "--route for a decision stored elsewhere",
            reason=ERROR_REASON["ROUTE_DECISION_MISSING"],
            code=EXIT_CONTRACT,
            work_order=order,
            ledger=str(route_decisions_path(root)),
        )
    window = decision_freshness_minutes() if freshness_minutes is None else freshness_minutes
    recorded_at = str(entry.get("recorded_at", ""))
    age_minutes = (dt.datetime.fromisoformat(utc_now()) - _parse_moment(recorded_at)).total_seconds() / 60
    if age_minutes > window:
        raise fail(
            f"The routing decision for {order!r} was recorded {int(age_minutes)} minutes ago and the freshness "
            f"window is {window}; the routes it scored can have swapped availability since. Re-run route",
            reason=ERROR_REASON["ROUTE_DECISION_STALE"],
            code=EXIT_CONTRACT,
            work_order=order,
            recorded_at=recorded_at,
            freshness_minutes=window,
        )
    return entry


def resolve_decision_for(root: Path, packet: dict[str, Any], route_value: str | None) -> dict[str, Any]:
    """The routing decision authorising this packet, from the ledger or an override."""
    if route_value:
        override = Path(route_value).expanduser().resolve()
        return {
            "decision": load_json(override),
            "source": str(override),
            "recorded_at": None,
            "canonical_work_order": None,
        }
    entry = resolve_route_decision(root, str(packet.get("work_order", "")))
    return {
        "decision": entry.get("decision") or {},
        "source": str(route_decisions_path(root)),
        "recorded_at": entry.get("recorded_at"),
        "canonical_work_order": str(entry.get("canonical_work_order", "")),
    }


def route_drift(decision: dict[str, Any], live: list[dict[str, Any]]) -> list[str]:
    """Every way the routes available now differ from the ones the decision was scored against.

    A decision records what was reachable when routing ran. Admission happens
    later, and in between an editor can open or close, a server can stop
    answering, or a lane can change hands. Acquiring on the recorded answer alone
    would hold protection for a route that is no longer the one being used.
    """
    recorded = {str(item.get("capability")): item for item in decision.get("tool_access", [])}
    drift: list[str] = []
    for item in live:
        name = str(item["capability"])
        was = recorded.get(name)
        if was is None:
            drift.append(f"capability {name!r} is required now but the decision never scored it")
            continue
        if bool(was.get("bound")) != bool(item["bound"]):
            state = "bound" if item["bound"] else "unbound"
            drift.append(
                f"capability {name!r} was {'bound' if was.get('bound') else 'unbound'} when routing ran and is "
                f"{state} now"
            )
            continue
        if item["bound"] and was.get("lease") != item.get("lease"):
            drift.append(
                f"capability {name!r} resolved to lease {was.get('lease')!r} when routing ran and to "
                f"{item.get('lease')!r} now"
            )
    return drift


def work_orders_path(root: Path) -> Path:
    return root / ".forge" / "state" / "work-orders.json"


def record_dispatch(root: Path, packet: dict[str, Any], admission: dict[str, Any], leases: list[dict[str, Any]]) -> dict[str, Any]:
    """Write the order transition in the same breath as the acquisition that earned it."""
    path = work_orders_path(root)
    order = str(packet.get("work_order", ""))
    entry = {
        "work_order": order,
        "status": "DISPATCHED",
        "revision": packet.get("revision"),
        "role": packet.get("role"),
        "dispatched_at": utc_now(),
        "lanes": [str(item.get("lane")) for item in leases],
        "leases": [str(item.get("lease_id")) for item in leases],
        "isolation_mode": str((packet.get("isolation") or {}).get("mode", "")),
        "route_source": admission["source"],
        "route_recorded_at": admission["recorded_at"],
    }
    with executor.StateMutex(root, state_path=path) as _mutex:
        document = load_json(path) if path.is_file() else {"schema": "forge.work-orders/v1", "orders": []}
        document.setdefault("schema", "forge.work-orders/v1")
        document["orders"] = [
            item for item in document.get("orders", []) if str(item.get("work_order")) != order
        ] + [entry]
        document["updated_at"] = entry["dispatched_at"]
        executor.write_state_atomically(path, document)
    return entry


def _parse_moment(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


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
                    "tool_surface": None,
                    "tools": [],
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
                "tool_surface": contract.get("tool_surface"),
                "tools": catalog_tool_names(contract.get("provider"), [name]),
                "detail": contract.get("detection_note"),
            }
        )
    return resolved


def strictest_isolation(modes: set[str]) -> str | None:
    ranked = [mode for mode in ISOLATION_STRENGTH if mode in modes]
    return ranked[-1] if ranked else None


def route_conflicts(packet: dict[str, Any], decision: dict[str, Any], work_order: str | None = None) -> list[str]:
    """Every way a packet contradicts the routing decision that authorised it.

    Routing resolves which lanes the work needs and how strongly it must be
    isolated. A packet that holds less than that would run outside the protection
    routing decided it required, which no lease can detect after the fact.

    Pass `work_order` when the packet names an alias: the registry treats aliases
    as display compatibility, so one must not read as a different work order.
    """
    conflicts: list[str] = []
    order = str(work_order or packet.get("work_order", ""))
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


def unreal_shape_lane(task_class: str, policy: dict[str, Any]) -> str | None:
    """The lane route-policy's unreal_routing implies for this shape of work."""
    routing = policy.get("unreal_routing", {})
    if task_class in set(routing.get("prefer_editor_closed_for", [])):
        return "lane.ue-editor-closed"
    if task_class in set(routing.get("prefer_live_editor_for", [])):
        return "lane.ue-editor"
    return None


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
    requested_order = str(request["work_order"])
    resolved_order = canonical_order(packet_registry, requested_order)
    if resolved_order not in packets:
        raise fail(f"Unregistered work_order {requested_order!r}; register the canonical packet or an explicit alias before routing", reason=ERROR_REASON["CONTRACT_INVALID"])

    policy = route_policy()
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
    shape_lane = unreal_shape_lane(str(request["task_class"]), policy)
    shape_conflict = {
        lane
        for lane in set(request.get("required_lanes", [])) | set(lanes)
        if lane.startswith("lane.ue-editor") and lane != shape_lane
    } if shape_lane else set()
    return {
        "schema": "forge.route-decision/v1",
        "project": str(root.resolve()),
        "request": request,
        "canonical_work_order": resolved_order,
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
            + (
                [
                    f"route-policy puts task class {request['task_class']!r} on {shape_lane!r}, and this request "
                    f"names {sorted(shape_conflict)!r}; the two Unreal lanes are mutually exclusive, so confirm the "
                    "shape of the work before taking a lane it does not imply"
                ]
                if shape_lane and shape_conflict
                else []
            )
        ),
        "requires_independent_verification": True,
    }
