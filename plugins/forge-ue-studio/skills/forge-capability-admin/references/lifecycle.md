# Capability lifecycle

Use this order:

```text
DISCOVER -> CLASSIFY -> CONSENT -> PROBE -> EVALUATE -> QUALIFY -> ACTIVATE
       -> MONITOR -> INVALIDATE -> RE-PROBE or DEACTIVATE
```

The manifest records capability type, provider, executable surfaces, permissions, integrity, provenance, licence, health, qualification, effective cost, context cost, lane, enabled steps, fallbacks, acceptance suites and invalidation triggers.

Qualification is a tuple:

```text
provider + exact version/model + task class + complexity + required capabilities
+ environment fingerprint + acceptance suite
```

An evaluation for document extraction does not qualify code review, image judgment, tool use, Unreal mutation, mesh construction or animation. A multimodal input capability does not imply image, video or mesh generation.

Activation is transient. Prefer the smallest tool/skill/MCP surface for the current phase and packet, measure the current host's actual context cost, and remove duplicate surfaces.
