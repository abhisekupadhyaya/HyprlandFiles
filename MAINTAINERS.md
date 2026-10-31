# Maintainers and project governance

HyprlandFiles is an independent Ubuntu project. The owner of this repository is
its initial maintainer. Contributors are welcome; review rights and release
responsibilities are granted explicitly as the project grows. No affiliation
with Ubuntu, Hyprland or Omarchy is implied.

Maintainers review compatibility, authentication/lifecycle changes, dependency
sources, licenses, recovery and evidence of acceptance. A passing unit suite is
required but cannot replace clean-machine or physical hardware tests. Root/login
changes need a human review even when CI is green. Do not merge your own security-
sensitive installer changes without another review when another maintainer is
available; otherwise document that limitation in the release notes.

Use feature branches and pull requests. Keep main reviewable and releasable;
never force-push published release tags. Dependency updates arrive as reviewed
changes, not silent installer substitutions. Disagreements are resolved from
reproducers and test evidence; conduct expectations are in CODE_OF_CONDUCT.md.

Repository-hosting settings are separate from files in Git. Before public launch,
the owner should enable branch protection / required CI, secret scanning where
available, and private vulnerability reporting, and confirm the security contact
route. This checkout does not claim those remote controls are already enabled.
See docs/releases.md for release gates and SECURITY.md for sensitive reports.
