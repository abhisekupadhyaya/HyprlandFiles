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
[release-preparation.json](release-preparation.json): 146 tests pass, including
real locked-wheel palette generation, the Server mode menu command, local greetd
entrypoint checks, terminal payload rollback, offline Cargo staging, archive
validation and vendor reproducibility. Appearance tests use a private schema and
Gio memory backend; no installed desktop preferences are changed. The real
219-crate Wiremix vendor archive was rebuilt without network access and produced
the exact locked SHA256. Wiremix also completed its real offline release build
on the installation host, and the installed binary reports version 0.11.0.

Two patched greeter builds were identical and matched the Git recovery manifest.
All 36 real retained inputs verify, including .deb package identities. Six old
PPA pool URLs returned 404; the original Launchpad build files matched the existing
hashes and their reviewed build URLs are now retained. Source-only installs can
use these exact archives when APT no longer lists a pinned version.

Native Hyprland, Fuzzel and Ghostty checks now pass for both profiles using
private rendered configurations and runtime directories. The installed user's
Lua configuration also passes. This validates parsing, not physical login or
display behavior. PRs #2 and #3 had passing GitHub runs and are merged. The
terminal-first feature run did not start because GitHub reported an account
billing lock; no passing rc.3 CI run is claimed. Login/installer changes still
require independent human review.

The host's first user phase stopped on immediate appearance readback after both
preferences had been saved. Verification now processes pending backend
notifications with a bounded wait and still rejects a permanent mismatch. Both
installed preferences read back correctly. System and user payloads are installed;
the controller was enabled and the owner rebooted. Doctor also reports an
existing network-wait failure from before installation; it was not reset or
changed to manufacture a passing result.

The first post-install login reached Hyprland without activating its helper
target. Activating the target restored the wallpaper and bar, confirmed by the
owner. Startup now explicitly imports the authenticated compositor environment
and activates the graphical target; shutdown and supervisor cleanup stop it.
Menu applications and logout use independent scopes. A disposable live systemd
test confirmed that the application scope survives stopping its launching
service, without running desktop actions. Fresh login and complete Server mode
acceptance with this repair still require physical verification.

The optional black/blue Bash add-on has been applied on the existing host.
Ghostty's merged configuration reports a black background with 0.8 opacity,
opaque ribbon cells and `/bin/bash`. The compact prompt shows `user@host`,
project/folder, Git and active environment context above a fixed input marker.
Timing is conditional above two seconds and failures show a red marker/exit code.
Python virtualenv/Conda/pyenv/direnv and project-scoped Node context use exported
activation variables without interpreter probes. Four optional native tests use
the checksum-verified retained Oh My Posh executable; they skip when that input
has not been prepared. Spy interpreters verify that environment badges do not
execute them, including after NVM switches. Long Git labels are abbreviated and
Git hides below 110 columns to make room for identity and environment context.
Existing font files, family, size and line height were verified unchanged during
the style-only update. The installed Hyprland config passes its isolated native
parser, and the existing compositor accepted size 7 / 3-pass blur on config reload.
Both local and Remote SSH VS Code settings select the same Bash profile and
terminal palette. Actual interactive pseudo-terminal tests
using the installed Ghostty and VS Code integration scripts preserve their OSC
hooks; accepting and executing a harmless history suggestion passes in both
contexts and with tmux's terminal type. Real Python environment activation and
deactivation, failure status and ble.sh transient header boundaries also pass
through all three startup paths. Repeated headers collapse without another
prompt-renderer invocation. A local interleaved benchmark of 24 measured renders
per case, after three warmups, observed about 8 ms in the home directory and
12–14 ms in the repository, including an active virtualenv. This measures the
renderer process, not SSH latency; the previous theme measured similarly.
JSONC preservation, file permissions and
reapplication without changes are covered. The owner reports adding the three
application-scoped VS Code glass controls to the separate client's local User
Settings; Remote SSH cannot apply those controls. Actual GUI appearance of the
new frosted style remains unconfirmed. A local preview renders real prompt output
with the existing font; its frosted backdrop is illustrative, not a live screenshot.

**Release gates still open:** actual clean Ubuntu Server install through APT,
manual boot/TTY/authentication/lifecycle tests of this portable layout, broader
GPU/desktop/VM testing, and off-machine retention/public distribution of the prepared
recovery archive. The existing-host installation and owner-driven reboot do not
substitute for these gates. Do not relabel this RC production-validated until
those gates have evidence.


Automatic default profile selection and the Git-anchored kit remain supported.
The rc.3 kit has 36 inputs, including the four terminal sources and the complete
Wiremix vendor archive. It is prepared and verified in the ignored local cache;
off-machine retention and distribution are not claimed. Recovery/tamper/missing/
symlink and deterministic source-plus-kit fixture tests pass. No fresh-system
root installer or physical lifecycle test was executed by this preparation.
A retained kit reduces archive-availability risk; it does not expand OS
compatibility or substitute for clean-machine acceptance.
