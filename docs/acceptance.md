# Physical acceptance per installation

Passing unit tests or installing packages does not complete hardware acceptance.
Keep TTY recovery and SSH usable, save work before each logout/reboot and obtain
the operator's approval. Never send passwords to a log or issue.

- [ ] Native `Hyprland --verify-config` and `./install.sh doctor` pass; no failed
      system/user units. Confirm actual output resolution, scaling and renderer
      (`glxinfo -B` if mesa-utils is already installed; do not infer from a GPU name).
- [ ] Open-lid boot automatically shows the username chooser. Select the intended
      user, try a wrong password (desktop must remain inaccessible), then login.
      Test Ctrl+Alt+F2 requires authentication; Ctrl+Alt+F7 returns to GUI.
- [ ] Kitty, launcher, fonts, notifications, clipboard, audio and physical keys
      work. Confirm a real application authentication prompt through the agent,
      without installing a special checker merely for appearance.
- [ ] Select a real file in a portal chooser and test a normal application's
      screen sharing. Interface availability alone is insufficient.
- [ ] Change wallpaper; all selected user components change together. Restart
      preserves the selected image and palette without regeneration delays.
      Root-owned login snapshot remains separate by design.
- [ ] Lock rejects a wrong password and unlocks normally. Close/reopen preserves
      a recognizable app and locks securely; screen blanking alone is insufficient.
- [ ] Server mode gracefully closes apps, hides login while lid stays open, and
      leaves no desktop/greeter/audio helpers for at least 30 seconds. Verify SSH
      actually responds, then close/open lid and confirm login reappears.
- [ ] With explicit reboot approval, AC and working SSH, reboot while closed.
      Reconnect remotely while still closed; inspect no graphics/audio processes
      and healthy server services for 30 seconds. Opening should then show login.
- [ ] No duplicates, restart loops or new failed services across transitions.
      Record failure logs; do not use reset-failed or mask exit codes to get PASS.
- [ ] Measure comparable headless/desktop workloads, MemAvailable, CPU/GPU activity
      and temperatures over useful intervals. Do not equate one idle reading with
      zero overhead or sustained thermal safety. Check battery physical condition
      and external monitor wiring when available; no destructive drain tests.
- [ ] Test normal recovery and per-file rollback in a disposable installation.
      Mark unavailable/untested cases honestly; freeze only after acceptance.

Desktop-profile machines omit lid-specific cases but still need authentication,
TTY, server-mode restoration with `hf-desktop on`, reboot and hardware checks.
Internet-free local login is tested separately in a window where disconnecting
network will not lose required remote access. Installer never changes networking.
