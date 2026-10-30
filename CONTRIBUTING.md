# Contributing

Start with an issue describing the concrete behaviour, Ubuntu version, CPU
architecture and relevant GPU/connector facts. Redact account names, network
addresses, SSIDs, credentials and unrelated logs. Include a minimal reproducer.

Use a branch and small reviewable changes. New hardware/release support needs
preflight detection, an exact compatible package lock, fallback/recovery,
meaningful isolated tests and actual clean-machine evidence. Do not add a driver
installer, remote root script, shell replacement or network migration as a
cosmetic dependency. Preserve per-file backup/idempotence/conflict semantics.

Run `./scripts/check.sh` without sudo. For extended palette tests on Linux x86_64
Python 3.14, run `python3 tools/prepare_dev.py`, then check again. A greeter rebuild
is `python3 tools/build_greeter.py`; it fetches a checksum-verified base .deb and
writes only `.cache`. Native config validation and live hardware acceptance
belong in a disposable system; never log out a contributor's desktop in CI.

Do not commit backups, inventory of a private machine, caches, package binaries,
virtual environments, tokens or licence keys. Do not add .git hooks automatically.
CI has read-only repository permissions and does not install this desktop.
Changes to root lifecycle code require race/teardown/recovery tests and a
separately approved human hardware test window.

Document validation honestly. A simulation, successful package installation,
running process, or synthetic password test is not physical acceptance. Keep
failed observations and limitations in release notes. Contributions are licensed
under MIT; keep any third-party attribution and redistribution obligations.
