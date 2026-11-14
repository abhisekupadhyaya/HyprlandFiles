# Changelog

## 0.1.0-rc.3 — 2026-11-13

- Use compact project/Git ribbons above a fixed input marker, with conditional
  environment badges, failures and slow-command timings. Collapse repeated
  headers in scrollback while retaining directory/environment boundaries. Keep
  a blank line between command blocks even after history compaction;
  resolve Python/Conda/pyenv/direnv and NVM context without interpreter probes.
- Add black-tinted Ghostty glass and stronger Hyprland blur; preserve existing
  typography with `--style-only`. Export VS Code's native glass settings for the
  separate client application.
- Add an opt-in shared Bash prompt, history suggestions and opaque black/blue
  styling for Ghostty and local/Remote SSH VS Code. Preserve JSONC, unrelated
  shell settings and existing permissions; retain exact add-on input hashes.
- Activate desktop helper services from the ready authenticated compositor;
  clean up graphical targets and environment on logout or compositor exit.
- Run menu applications and graceful logout in independent user scopes so
  stopping Waybar cannot interrupt logout or kill launched terminals.
- Isolate native configuration probes from the installed desktop's user bus.
- Remove PipeWire filter-chain default-target activation so a closed-lid boot
  cannot start desktop audio through its dependency on PipeWire.
- Wait for GSettings backend notifications before appearance readback, while
  retaining errors for persistent mismatches. Native checks use a private runtime
  directory and work from SSH sessions without XDG_RUNTIME_DIR.
- Provide a terminal-first desktop with Ghostty, Yazi, Superfile, Wiremix,
  Bluetui, tmux and btop; retain authenticated login and both lifecycle profiles.
- Fix the Server mode menu command and restrict the managed session launcher
  to authenticated local greetd sessions; cover cancellation and rejected entrypoints.
- Retain four TUI inputs and all 219 Wiremix registry crates in the 36-artifact
  recovery kit. Build Wiremix offline with a private Cargo vendor configuration
  as the desktop user; preserve binary backups, conflicts and rollback.
- Recover six superseded PPA packages through their original Launchpad build
  files with unchanged hashes; use exact verified archives when APT no longer
  lists a pinned version.
- Exercise kit/online staging, build failures, archive validation and vendor
  reproducibility. Use a private GSettings schema for minimal-host tests.
- Update CI action pins through reviewed PRs #2 and #3. Clean-machine, native
  compositor and physical hardware acceptance of this candidate remain open;
  the login/installer changes still require independent maintainer review.

## 0.1.0-rc.2 — 2026-10-31

- Default to dark OS/application appearance through per-user GSettings, GTK3/4
  defaults and the standard desktop Settings portal.
- Seed fresh VS Code preferences with Dark Modern and automatic OS appearance;
  preserve existing application settings and unrelated GTK keys/comments.
- Back up only the two changed desktop preference keys, with exact per-key
  rollback and later-edit conflict checks; never snapshot a whole dconf database.
- Keep appearance dependencies to Ubuntu schema/backend packages, without adding
  a full desktop or changing wallpaper-generated component colours.

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
