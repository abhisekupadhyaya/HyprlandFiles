# Deliberate desktop updates

Initial ABI pins select the exact compatible Hyprland stack and the privacy-
patched greeter in the release lock. The greeter privacy pin is active from
installation, even before final desktop-tool acceptance.
After **local physical acceptance**, `sudo python3 tools/installer.py freeze`
adds exact pins for the desktop tools as well. The command checks every installed
version and snapshots the pin file. It installs/removes nothing and restarts
nothing. These pins do not cover the kernel, Mesa, systemd, PAM, OpenSSH,
networking or other shared Ubuntu security infrastructure.

Review desktop upstream security advisories promptly and review locks at least
monthly. A freeze creates a maintenance obligation; it does not make old software
secure forever. Keep Ubuntu security/unattended updates enabled. Do not use
`apt-mark hold '*'`, disable unattended upgrades or broadly prefer all PPA packages.

For a release update:

1. Create a branch, review release-specific Hyprland APIs and new package sources,
   update one OS/architecture lock and the reviewed source key only when needed.
2. Cache both current and candidate .debs before changing the running machine.
   Use signed APT metadata; record SHA256 and upstream/source licenses. Locks in
   Git do not guarantee future archive availability. Retain the original pinned
   Python wheels and patched greeter base package too.
3. Rebuild/review nwg-hello privacy/IPC patches; never replace the patched client
   with the old credential-logging Ubuntu version. The lock version has `+hf1`.
4. Run all offline tests, build twice and compare package bytes, validate Lua,
   then install on a clean disposable Ubuntu Server image. Package simulation
   must show no removals or unrelated infrastructure changes.
5. With saved work/recovery access, perform the whole acceptance checklist on
   supported hardware, including closed boot and wrong-password/TTY tests. Record
   actual results, failures, resource measurements and limits in a release note.
6. Create a reviewed migration with snapshot rollback and explicit approval for
   lifecycle/service changes; then freeze the **tested installed versions**.

Do not loosen the install lock to “latest” when a version disappears. Publish a
new tested lock/release instead. The initial Pillow 13 / colorthief combination
has an upstream deprecation for Pillow 14; its adapter and wheel lock need review
before that upgrade. No package-removal cleanup is part of this process.

To undo only an unchanged final tool-pin transaction, run the exact rollback
command printed by freeze. Root rollback currently requires no graphical session
and a stopped controller; schedule it with the same saved-work discipline. Other
ABI pins remain until their own source-stage rollback or reviewed update.
