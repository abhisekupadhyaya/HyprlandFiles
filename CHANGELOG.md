# Changelog

## 0.1.0-rc.1 — 2026-10-30

- Extract the working Ubuntu/Hyprland configuration into a public portable project.
- Add one-command staged installer, read-only plan/doctor, per-file transactions,
  conflict refusal, interrupted-write recovery and explicit snapshot rollback.
- Add desktop and optional laptop/server profiles with hardware detection,
  configurable keyboard/scale/GPU and preserved network/driver/security policy.
- Include original blue artwork, coordinated pywal16 theme and Mac-like shortcuts.
- Carry the reviewed selectable-user login privacy/IPC patch with reproducible build.
- Add exact ABI/Python locks, tests, CI and contributor/security/source documentation.
- Mark clean-machine portable installation and physical acceptance as release gates.

### Reinstall reproducibility follow-up

- Detect the default laptop/server or desktop profile automatically.
- Preserve 33 verified artifacts with a Git-anchored recovery manifest and an
  optional source-plus-kit archive that still installs with one shell command.
- Use archived desktop packages/wheels without adding the PPA or rebuilding the
  greeter; preserve ordinary Ubuntu dependency/security-update handling.
- Reject unrelated upgrades even when APT and dpkg format architecture suffixes
  differently; add tamper, missing-file, symlink and deterministic-archive tests.

### Public project maintenance

- Document maintainer/reviewer roles, versioning, explicit migrations, release
  gates and support roadmap; add CODEOWNERS without claiming branch protection
  is already enabled on the hosting service.
- Add a reproducible SPDX 2.3 input inventory for the recovery kit and a CI
  consistency check; do not claim full OS coverage or guessed package licences.
