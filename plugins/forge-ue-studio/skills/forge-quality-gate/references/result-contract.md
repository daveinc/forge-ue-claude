# Attempt result contract

Return:

- work order, attempt, provider and verdict;
- observed facts and separately labelled inferences;
- findings ordered by severity with exact artifact/location when possible;
- touched files/assets/packages and undeclared changes;
- evidence artifacts and verification commands/results;
- untested areas, residual risk and next action.

Use `PASS`, `FAIL`, `PARTIAL`, `BLOCKED` or `INDETERMINATE`. Say explicitly when there are no findings. Do not hide malformed output, missing evidence, tool stderr or an inability to verify.
