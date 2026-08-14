# Capability classification

| Status | Meaning |
|---|---|
| `AVAILABLE_VERIFIED` | A current safe probe passed for this version, route, and task class. |
| `AVAILABLE_UNVERIFIED` | Detected, but usable behavior is not proven. |
| `UNAVAILABLE_OPTIONAL` | Related workflows degrade or fall back. |
| `UNAVAILABLE_BLOCKING` | The named milestone cannot safely start. |
| `STALE` | Prior proof was invalidated by version, path, schema, plugin, hardware, or script change. |

Record verified facts under results and uncertain interpretations under assumptions. Never convert “installed,” “enabled,” “open,” or “free” directly into competence.
