<!-- forge:workflow
name: visual-production
consumes: visual pillars, story beat, camera and use case, references, gameplay interface, platform budget
produces: asset manifest, asset interface, camera-locked evidence
-->

# Forge Visual Production — workflow

<purpose>
Take a visual requirement to an integrated, evidenced asset across the Blender and Unreal routes.
</purpose>

<core_principle>
Qualify each visual capability separately and never infer one from another. Never let a provider own
an art seat.
</core_principle>

<process>

<step name="load_scope" priority="first">
Read only the relevant visual pillars, story beat, camera and use case, references, gameplay
interface and platform budget.
</step>

<step name="separate_capabilities">
Treat these as distinct capabilities: visual direction, prompt and reference decomposition, raster
generation, video and previs planning, 3D construction, rigging and animation, integration, critique.

**Never infer one from another.**
</step>

<step name="build_references">
Create licensed reference and negative-reference sets.

Use the resident host's visual generation for controlled art, photo and board candidates where
exposed, and visual-direction skills for character sheets, turnarounds, storyboards, shot cards and
continuity contracts.

Offload bounded variants to a qualified worker and preserve provenance.
</step>

<step name="approve_direction">
Stop for human approval of the primary direction. Never treat a generated concept as a shipping asset
by default.
</step>

<step name="declare_asset_interface">
Produce orthographic and turnaround requirements plus the asset interface: scale, pivot, collision,
skeleton, sockets, materials, animation events, LODs, budgets.
</step>

<step name="choose_route">
Compare available Blender and Unreal routes using
[visual-routing.md](../skills/forge-visual-production/references/visual-routing.md).

Permit a qualified worker and a split route when it improves context use, throughput or quality.
</step>

<step name="build">
Build blockout, mesh, UV and material, rig, skin and animation on the selected route with asset-class
checkpoints.

Preserve native source and versioned export settings.
</step>

<step name="integrate">
Integrate in Unreal through the appropriate native MCP, live Python or editor-closed route. Run
structural, animation, reference, memory and performance checks.

Capture camera-locked evidence. Compare objective requirements in visual QA and leave subjective
likeness, style and appeal to the human art owner.

> **Why:** CHANGELOG.md 0.4.0 § *All three Unreal routes exist, and the verb that reports them says so*
</step>

<step name="promote" priority="last">
Promote the asset manifest, or reactivate the last valid placeholder.

Invalidate gameplay only when a declared asset interface changed.

Use `forge-gameplay-gauntlet` for bounded in-game comparison after integration.

Credit the actual route that created and verified each artifact.
</step>

</process>
