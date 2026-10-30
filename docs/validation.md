# Validation status

Version 0.1.0-rc.1, 2026-10-30. This document distinguishes configuration heritage
from validation of the new portable installer.

The originating configuration ran on Ubuntu Server 26.04 amd64, Hyprland 0.57,
Intel i915/Mesa acceleration, a 4K panel at 2x and an unused nouveau GPU runtime-
suspended. Authenticated desktop login, open/closed-lid reboot, clean Server mode,
real lock with wrong-password rejection, same-session lid app preservation,
wallpaper persistence, file-picker selection and physical audio/brightness
controls were exercised during development. This is evidence for the original
setup, not a fresh installation of this portable release on arbitrary hardware.

The final selectable-user frontend has a successful open-lid boot/login and
confirmed user dropdown. Its physical incorrect-password/TTY and post-change
Server-mode/closed-boot retests remain open. Longer actual-app screen sharing,
new auth-agent prompt, offline-login disconnection, external display and sustained
thermal/battery checks are also not claimed complete.

Portable automated coverage includes the six lifecycle transitions and races,
permission-preserving rollback, dangling symlinks, conflict refusal, interrupted
writes, duplicate/idempotent deploys, unsupported platforms, input validation,
APT-removal rejection, wheel path traversal, different GPU/card/connector layouts,
fragmented login IPC and synthetic wrong-password handling. Complete system/user
payload deployment and restoration run against disposable filesystem trees.
Extended tests exercise real pywal16 palette generation and cross-component
outputs; Unix socket readiness uses a private temporary socket.

Native Lua parser, deterministic patched package builds and locked wheel checks
are additional local integration checks. Automated results are recorded in
[release-preparation.json](release-preparation.json): 88 tests passed, native Lua
and Fuzzel validation passed for both profiles, controller unit syntax passed,
and two patched greeter builds were identical; CI execution is not claimed until GitHub runs it.

**Release gates still open:** actual clean Ubuntu Server install through APT,
manual boot/TTY/authentication/lifecycle tests of this portable layout, broader
GPU/desktop/VM testing, and off-machine retention/public distribution of the prepared
recovery archive. No root install, logout or reboot of the developer's running desktop is
performed while preparing this repository. Do not relabel this RC production-
validated until those gates have evidence.


A follow-up added automatic default profile selection and a verified 33-artifact
recovery kit anchored in Git. The kit is actually prepared and verified locally;
recovery/tamper/missing/symlink and deterministic source-plus-kit packaging tests
pass. No fresh-system root installer or physical lifecycle test was executed by
this preparation. A retained kit reduces archive-availability risk; it does not
expand OS compatibility or substitute for clean-machine acceptance.
