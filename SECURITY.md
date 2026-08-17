# Security

Report security issues privately to the repository owner.

Forge records only whether a credential is present. It must never print, persist, or commit secret values. Project mutation requires an explicit apply action; optional package, plugin, model, API, PATH, and system changes remain separate user-approved operations.

## Forge is a permission model, not a sandbox

This distinction matters most for anyone considering running Forge unattended, so it is stated plainly rather than left to be inferred.

**What Forge does contain.** Every machine-wide change is previewed before it is applied, backs up the file it replaces, preserves entries it did not write, and records consent. Nothing installs packages, downloads models, enables engine plugins, changes `PATH`, writes credentials or edits the project descriptor without a separate explicit approval. Isolation between concurrent writers is enforced transactionally: lane leases with real owners, Git worktrees, and `git lfs lock` against the actual server. A resource Forge could not free keeps its lane quarantined rather than being reported as released.

**What Forge does not contain.** None of the above is a security boundary. Forge does not provide process isolation, filesystem confinement, network egress control, or privilege separation. The resident runtime it orchestrates — Claude Code, Codex, or another host — holds broad filesystem and shell authority on the account it runs as, and Forge's agents inherit it. `unreal-operator` needs `Bash` to run commandlets, which is by itself enough to reach anything that account can reach. Forge constrains what its own workflows *ask* for; it cannot constrain what the runtime is *able* to do.

On a personal workstation, where the operator is present and the account is their own, this is the normal posture for an agentic coding tool and the permission model is the right layer.

**For autonomous or production-line operation**, where an agent runs for long stretches without a human watching, the containment has to come from the operating system, not from Forge:

- a dedicated worker account, not the developer's own login
- filesystem ACLs limiting that account to the project tree and its build outputs
- credentials scoped to that worker and rotatable independently
- network egress policy, so a compromised or confused agent cannot reach arbitrary hosts
- an ephemeral runner or VM for build, cook and shader work, rebuilt from a known image
- backups and version control that the worker account cannot rewrite

Treat Forge's permission model and OS-level containment as complementary. Neither substitutes for the other, and only the second survives an agent behaving in a way nobody anticipated.
