<!-- forge:workflow
name: plan-convergence
consumes: the phase plan, .forge/capabilities/qualifications.json
produces: revised plan, review cycle record
-->

# Forge Plan Convergence — workflow

<purpose>
Drive a plan to zero actionable findings through independent review cycles, or stop and escalate.
</purpose>

<core_principle>
Never silently proceed past a stall, a malformed reviewer output or an unverifiable source.
</core_principle>

<process>

1. Require a plan carrying scope, dependencies, work packets, write sets, lanes, acceptance, verification, fallbacks, human gates, and declared new artifacts.
2. Select independent reviewers from currently qualified lanes. Keep at least one isolated from planner reasoning.
3. Ground every cited symbol, asset, plugin, API, path, capability and acceptance command against source or a verified registry. Exclude artifacts the plan says it will create.
4. Record findings by severity. Return only current-cycle `HIGH` and actionable non-high counts; keep prior cycles as audit history and never re-count resolved findings.
5. Revise the plan so every actionable finding becomes a task, acceptance item, verified closure, explicit deferral, or reasoned rejection.
6. Repeat until both counts reach zero, the cycle limit is reached, or counts stop decreasing.
7. Stop and present remaining concerns to the human owner on a stall, malformed reviewer output, unverifiable source, or cycle exhaustion. Never silently proceed.

</process>
