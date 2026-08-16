"""Which provider earns a bounded work order, and on what evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_core import ERROR_REASON, EXIT_USAGE, RESIDENT_PROVIDER, fail, load_json, plugin_root, project_root
from forge_hosts import active_profile


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

    candidates = [
        {
            "provider": RESIDENT_PROVIDER,
            "host": profile["id"],
            "eligible": True,
            "score": 0.0,
            "reason": f"resident baseline ({profile.get('display_name', profile['id'])})",
        }
    ]
    required_capabilities = set(request.get("required_capabilities", []))
    required_lanes = set(request.get("required_lanes", []))
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
        "requires_independent_verification": True,
    }
