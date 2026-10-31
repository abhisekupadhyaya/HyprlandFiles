# Installation and configuration

## Supported starting point

Ubuntu Server 26.04 amd64, systemd, Python 3.14 and `multi-user.target`; an
existing regular sudo-capable local account with a password. Default Ubuntu
`/home/name` paths are supported. Encrypted homes that are unavailable before
login, LDAP/SSSD/MFA/password-expiry PAM conversations and multiseat are outside
the initial support boundary. Local password authentication itself is offline.
Installation needs internet; authentication does not. Ubuntu universe must be
available in your existing official sources; if a package is unavailable, review
your Ubuntu sources rather than adding arbitrary repositories.

Inspect with `./install.sh plan`. Plan reads OS/package metadata and enumerates
conflicting managed paths without dumping their content. It does not invoke
sudo, write files, install packages or start services. Unsupported OS/architecture
fails without changes. `--help` and `version` work without installing anything.

## One-command setup

Run `./install.sh --profile desktop` or `./install.sh --profile laptop-server`
as the intended account, not root. `--yes` explicitly approves the printed plan
for unattended provisioning; it does not grant sudo access or bypass preflight.
Use `--adopt` only after reviewing existing individual files. An interactive
adoption also requires typing ADOPT. For an existing desktop, save work and log
out yourself: the installer refuses live graphical sessions or active display
managers and never stops them to make installation proceed.

The setup phases are:

1. System: verify support/session state; snapshot source/pin/mask changes; trust
   only the bundled PPA signing key for online installs; update signed APT
   metadata; build the patched greeter for online installs, or verify/use all
   preserved desktop binaries and wheels from a recovery kit; simulate APT and reject
   removals/existing unrelated upgrades; install locked desktop packages and
   missing Ubuntu dependencies; prepare hashed palette wheels; transactionally
   install the root-owned runtime and login/controller files without enabling
   or starting the controller. An incomplete package stage keeps the
   login service masked; recover with its printed snapshot.
2. User: generate a complete initial palette before linking it, preserving a
   valid existing choice on rerun; install individual rendered config files and
   native graphical-session enabling links; reload only user unit definitions;
   validate native Lua. Only after success, a final sudo phase enables the
   controller for **next boot**. No running desktop is reloaded or started.

If a system stage succeeds but the user stage fails, preserve the printed paths.
Fix the reported conflict and rerun `./install.sh user` with the same profile /
keyboard / scale options, then run `./install.sh enable`. Do not reboot into
the managed login until the user stage passes and enable completes. System and user snapshots are separate. Files under unrelated
paths and personal `~/.config/hypr/user.lua` are never overwritten.

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `--profile` | `auto` | Detect a readable laptop lid; otherwise desktop. Explicit overrides available |
| `--keyboard` | `us` | XKB layout, e.g. `gb` or `us,de` |
| `--scale` | `auto` | Automatic display sizing, or explicit 0.5–4 scale |
| `--gpu` | `auto` | Intel i915/xe preference, compositor `default`, or PCI ID |
| `--wallpaper` | Included blue still | Initial local image; cached choice is preserved on rerun |
| `--adopt` | Off | Explicit backup/replacement of conflicting managed files |
| `--yes` | Off | Noninteractive approval of the same setup plan |
| `--bundle` | Auto-detect `bundles/ubuntu-26.04-amd64` | Verify and use preserved desktop packages/wheels |

Keep the same system profile on rerun. Automatic profile migration is refused;
changing lid/power behaviour requires a separate reviewed migration.

The bar chooses network/battery/backlight devices dynamically. Backlight control
uses logind's authenticated session API and selects a native device if there is
one unambiguous choice. If multiple candidates remain, set `backlight_device` in
`~/.config/hyprlandfiles/settings.json` explicitly. External monitor brightness
is not implemented. No device groups, udev rules or passwordless privileges are
added. Network controls show status; configure networking with your existing
Ubuntu tools, not a replacement NetworkManager installation.

## More than one user

The chooser lists normal users with homes under `/home`; it is not an account
creation UI. As each additional regular account, run `./install.sh user` with
matching system profile/scale options before first login. The controller's
`allowed_users` in `/etc/hyprlandfiles/hyprlandfiles.conf` governs who can request
Server mode. An administrator must explicitly add other permitted account names;
restart the controller only in an approved window. Existing sessions are always
protected regardless of that allowlist. Custom PAM conversations need review.

## First boot and recovery

Save work and reboot manually when ready. The laptop lid policy takes effect
when logind next reads its configuration at boot. The installer does not restart
logind. Keep Ctrl+Alt+F2 and an existing SSH route available; Ctrl+Alt+F7 returns
to the login/desktop. Server services are not dependencies of the controller.
Run doctor and the full physical checklist before freezing additional tools.


## Default dark appearance

The user phase sets org.gnome.desktop.interface color-scheme to prefer-dark and
GTK theme to Adwaita-dark. It merges GTK3/4 settings while preserving other keys,
sections and comments, and seeds fresh optional VS Code settings with OS detection and an installed dark theme. Existing VS Code JSON/JSONC preferences and profiles are kept.
The GTK Settings portal publishes the preference to supporting applications;
apps with explicit overrides or their own theme mechanisms remain app-specific.
No global GTK_THEME environment override, new theme manager, desktop environment,
service restart or logout is needed. Some already-running legacy apps read their
GTK settings only at startup and apply them when next opened. The shell,
terminal, launcher and notifications keep their wallpaper-generated palette.

VS Code dark theme identifiers are detected from its installed built-in theme
metadata. If VS Code is not installed yet, only OS colour-scheme detection is
seeded; the app chooses its own compatible dark theme when installed later.
