# Visual routing

## Typical advantages

| Route | Likely advantage | Must prove |
|---|---|---|
| Blender | Independent DCC lane, broad mesh/UV/bake/rig tools, source portability | Gateway reliability, scale/export determinism, asset-class quality |
| Unreal | Control Rig, Sequencer, retargeting, procedural/in-engine authoring, less round-tripping | Editor-lane cost, deterministic save/readback, asset-class quality |

Benchmark representative tasks on quality, elapsed time, rework, GPU pressure, editor contention, and handoff cost. Re-rank after relevant version or hardware changes. A valid split may use Blender for mesh/UV and Unreal for rigging/animation, or the reverse when evidence supports it.

The resident host operates the selected route by default and can use exposed image generation for concepts and photos. Consider local workers for bounded variants, image-to-3D breakdowns, scripts, batch modelling steps or first-pass visual review when their asset-class and complexity eval passes. Charge briefing, verification and rework against claimed token savings.

Do not collapse these capabilities:

- visual direction and reference decomposition;
- raster generation/editing;
- storyboard, video prompt and previs planning;
- mesh/UV/material construction;
- rigging, skinning and animation;
- Unreal integration and in-engine capture;
- objective QA and human subjective approval.

A provider may qualify for any subset. Multimodal input does not imply raster, video, mesh or animation output.

## Objective acceptance

Check topology/non-manifold state, transforms, scale/pivot, UVs, color space, material slots, LODs, collision, skeleton hierarchy, influences, duration/loop/root motion, events, naming, export/save determinism, Unreal warnings, references, memory, and frame budgets.

Human approval owns style, likeness, appeal, and game feel.
