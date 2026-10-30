# HyprlandFiles

A coordinated Hyprland workstation on Ubuntu Server: wallpaper-generated colours,
a compact bar, Mac-inspired shortcuts and an authenticated username chooser.
An optional laptop/server profile keeps server workloads running with the lid
closed and starts graphical login when it opens.

![Original royal-blue wallpaper included with the project](assets/royal-blue.png)

**0.1.0-rc.1 — release candidate.** Ubuntu **26.04 amd64** is the initial target.
The configuration originates from a working installation; the portable installer
has isolated transaction, rollback, lifecycle and protocol tests. A clean-machine
end-to-end install is still a release gate. This is not a universal hardware or
production-certification claim. See [compatibility](docs/compatibility.md) and
[validation status](docs/validation.md).

## Install

Start with Ubuntu Server 26.04, working internet, a regular local account with a
password and sudo access, and a recovery TTY or existing SSH connection. Keep
Ubuntu's normal security updates enabled. Review the checkout before running it.

```sh
git clone https://github.com/abhisekupadhyaya/HyprlandFiles.git
cd HyprlandFiles
./install.sh plan --profile laptop-server
./install.sh --profile laptop-server
```

The default `./install.sh` detects a readable laptop lid and selects the
laptop/server profile; otherwise it selects a conventional desktop. Override
with `--profile desktop` or `--profile laptop-server` when appropriate. The installer shows its plan, asks for
explicit confirmation, then uses sudo for the system stage. It configures the
next boot; **you choose when to reboot**. Never use `curl | sudo sh`.

```sh
./install.sh plan --profile desktop --keyboard us,de --scale auto --gpu default
./install.sh --profile desktop --keyboard us,de --scale auto --gpu default
```

Scale defaults to EDID-based automatic sizing. GPU `auto` prefers an available
Intel i915/xe device and otherwise uses compositor selection; `default` leaves
selection entirely to the compositor. `--gpu PCI_ID` explicitly selects a present
GPU. No drivers, module settings, Secure Boot, boot parameters or GPU power
policy are changed. Hybrid external-output wiring needs a real monitor test.

Existing configs are refused if they conflict. Review/merge them, or explicitly
pass `--adopt` to back up and replace only the individual listed files. Whole
configuration directories are never replaced. Keep personal Lua additions in
`~/.config/hypr/user.lua`; the installer never writes that file. See
[installation](docs/installation.md) for stages, recovery and multiple users.

## What you get

- Hyprland **0.57.0 Lua** config, pinned as a compatible ABI stack; other Hypr
  tools retain their own supported configuration formats.
- **pywal16** colours derived from a still wallpaper, cached before login and
  coordinated across Hyprland, Waybar, Kitty, Fuzzel, notifications and hyprlock.
- The included original blue artwork; change it with **Super+Alt+W** or
  `hf-theme set /path/to/image.png`. Login uses a separate root-owned snapshot.
- Native greetd/PAM authentication, a username dropdown, focused password field,
  Intel-aware login rendering and a credential-redacted nwg-hello client.
- PipeWire audio, notification controls, file chooser/screen-sharing portals,
  clipboard tools, polkit agent, brightness/audio controls and recovery guide.
- Explicit **Lock**, **Log out**, **Server mode**, **Restart** and **Shut down**
  actions. Destructive session/power actions ask for confirmation.

### Laptop/server behaviour

| Event | Behaviour |
| --- | --- |
| Boot with lid closed | Server boot; no graphical login, compositor or desktop audio |
| Boot open / open after headless boot | Local authenticated login appears automatically |
| Close an existing desktop | Secure lock and internal display off; apps remain running |
| Reopen without reboot | Unlock the same session |
| Reboot while closed | Old desktop ends; server-only until lid opens |
| SSH login | Never launches a desktop |

This profile ignores lid suspend on **battery too**. It does not invent a safe
battery shutdown policy. Review power requirements and physical battery condition.
Unknown lid state fails closed. Desktop failure is independent of server units.
See the [lifecycle design](docs/lifecycle.md) and [acceptance checklist](docs/acceptance.md).

## Daily use

| Shortcut | Action |
| --- | --- |
| Super+Space | Search applications |
| Super+Return / Super+E | Terminal / files |
| Super+K | Shortcut and recovery guide |
| Super+C / Super+V | Copy / paste, with terminal-specific handling |
| Super+Ctrl+Q | Lock, preserving applications |
| Super+Escape | Session/power menu |
| Ctrl+Left / Ctrl+Right | Previous / next workspace |
| Super+Alt+W / Super+Alt+N | Wallpaper / notifications |
| Super+Shift+3 / Super+Shift+4 | Full / region screenshot to clipboard |

Touchpad/mouse natural scrolling is enabled. See [all shortcuts](docs/keybindings.txt).
No application launch depends on the original checkout remaining in your home.
The installed runtime is root-owned under `/usr/local/share/hyprlandfiles`.

## Verify, update and roll back

```sh
./install.sh doctor
# Only after the physical acceptance checklist passes:
sudo python3 tools/installer.py freeze
# Use the exact path printed before each transaction:
./install.sh rollback /exact/BACKUP/path
```

The installer refuses package removals and changes to existing unrelated
packages. Exact-version desktop packages can come from signed configured sources or the
verified recovery kit; it never silently substitutes a newer Hyprland release. PPA trust is
explicit. [Update procedure](docs/updates.md), [rollback](docs/rollback.md),
[security policy](SECURITY.md), [sources and licensing](THIRD_PARTY_NOTICES.md).

Networking/Netplan, SSH/Tailscale, firewall, disks, bootloader and driver policies
remain outside the installer. No telemetry, accounts, public ports, remote
publishing, shell replacements or remote dotfile installers are included.

## Keep a reinstall archive

Version pins are not a backup. A recovery kit retains all 28 locked desktop
packages, the patched greeter and original build input, and the three colour-
runtime wheels. Its 33 artifact hashes and package identities are checked against
[the manifest in Git](locks/recovery-ubuntu-26.04-amd64.json), not a manifest that
an untrusted download supplies for itself.

A prepared source-plus-kit release has the kit in `bundles/ubuntu-26.04-amd64`.
Extract it and run `./install.sh`; the installer detects the kit automatically.
There is no manual theme reconstruction or greeter build in the kit install path.
Keep a separate backup of that release archive. For a standalone retained kit:

```sh
./install.sh verify-bundle --bundle /path/to/recovery-kit
./install.sh --bundle /path/to/recovery-kit
```

The kit removes reliance on old desktop binaries staying in the PPA. Normal
Ubuntu dependencies still use signed Ubuntu repositories and security updates;
this is not a full offline OS image or cross-release ABI emulator. See
[reproducibility](docs/reproducibility.md) for retention and release preparation.

## Contribute

Read [CONTRIBUTING.md](CONTRIBUTING.md), [maintainer policy](MAINTAINERS.md),
[release gates](docs/releases.md) and the [roadmap](ROADMAP.md). Run `./scripts/check.sh` for offline
standard-library checks. Extended palette tests use checksum-verified locked
wheels: `python3 tools/prepare_dev.py`, then `./scripts/check.sh`. These commands
need no sudo and never activate login, log out, or reboot.

MIT for original code/config/artwork; retained upstream notices cover the small
nwg-hello patch/test fixture. Package/font licenses remain with their upstreams.
