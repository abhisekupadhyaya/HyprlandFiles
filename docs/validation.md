# Validation status

Version 0.1.0-rc.3, 2026-11-13. This document distinguishes configuration heritage
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

Current automated results are recorded in
[release-preparation.json](release-preparation.json): 116 tests pass, including
real locked-wheel palette generation, the Server mode menu command, local greetd
entrypoint checks, terminal payload rollback, offline Cargo staging, archive
validation and vendor reproducibility. Appearance tests use a private schema and
Gio memory backend; no installed desktop preferences are changed. The real
219-crate Wiremix vendor archive was rebuilt without network access and produced
the exact locked SHA256. Actual Wiremix compilation is not claimed complete.

Two patched greeter builds were identical and matched the Git recovery manifest.
All 36 real retained inputs verify, including .deb package identities. Six old
PPA pool URLs returned 404; the original Launchpad build files matched the existing
hashes and their reviewed build URLs are now retained. Source-only installs can
use these exact archives when APT no longer lists a pinned version.

Native Lua/Fuzzel and controller parser results from rc.2 are historical evidence;
they are not validation of this changed candidate. Hyprland, Fuzzel and Ghostty
native binaries are unavailable in this preparation environment, so rc.3 native
checks remain open. PRs #2 and #3 had passing GitHub runs and are merged. The
terminal-first feature run did not start because GitHub reported an account
billing lock; no passing rc.3 CI run is claimed. Login/installer changes still
require independent human review.

**Release gates still open:** actual clean Ubuntu Server install through APT,
manual boot/TTY/authentication/lifecycle tests of this portable layout, broader
GPU/desktop/VM testing, and off-machine retention/public distribution of the prepared
recovery archive. No root install, logout or reboot of the developer's running desktop is
performed while preparing this repository. Do not relabel this RC production-
validated until those gates have evidence.


Automatic default profile selection and the Git-anchored kit remain supported.
The rc.3 kit has 36 inputs, including the four terminal sources and the complete
Wiremix vendor archive. It is prepared and verified in the ignored local cache;
off-machine retention and distribution are not claimed. Recovery/tamper/missing/
symlink and deterministic source-plus-kit fixture tests pass. No fresh-system
root installer or physical lifecycle test was executed by this preparation.
A retained kit reduces archive-availability risk; it does not expand OS
compatibility or substitute for clean-machine acceptance.
