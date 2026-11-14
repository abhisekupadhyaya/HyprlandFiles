# Sources, attribution and redistribution

Original HyprlandFiles Python integration, Glade/CSS/Lua configuration and the
included original `assets/royal-blue.png` artwork are covered by the project MIT
license. The image was generated for this configuration from a cobalt ceramic /
architectural brief; it is not a wallpaper copied from another dotfile repository.
SHA256: f8639a0632c82d6737319d1024a627b09713ee395e348c1369bdf5eb2e9e9196.

Layout cues were reviewed from
[L3yzs/By-LeyzS-Arch-Hyprland-Dotfiles](https://github.com/L3yzs/By-LeyzS-Arch-Hyprland-Dotfiles)
at a9a03acac773ec1e826023e333ee1c155cccb7af: accent-edged groups, small corners,
wallpaper-led coordinated colours. No installer or wholesale config directory
is distributed here. Mac-like shortcuts use native Hyprland send_key_state,
reviewed against [Omarchy's hotkeys](https://omarchy.org/manual/hotkeys/);
no Omarchy application, panel or remapping daemon is bundled.

The nwg-hello patch and test fixture derive from Ubuntu's 0.4.2-1 source package
payload (upstream Piotr Miller, Debian packaging Maytham Alsudany). Both are MIT /
Expat; retained notices are in [LICENSES/nwg-hello.txt](LICENSES/nwg-hello.txt).
The fixture is only the reviewed native login method for synthetic tests. The
builder checks the original package SHA256 and applies the complete reviewed
diff. Rebuilt .debs retain upstream documentation/copyright metadata; Git does
not contain the package or full third-party source tree. Authentication remains
with greetd/PAM; the patch redacts payloads and fixes message framing.

Installed Hyprland, labwc, greetd, pywal16, Pillow, colorthief, fonts and other
packages remain governed by their upstream licenses. They are fetched from
configured signed APT repositories or hash-locked wheels, not relicensed under
this repository's MIT license. Public binary release artifacts must carry their
licenses and satisfy any applicable source-distribution obligations.

Primary release-specific sources:

- https://github.com/hyprwm/Hyprland/releases/tag/v0.57.0
- https://hypr.land/news/26_lua/ (other Hypr tools still use hyprlang)
- https://wiki.hypr.land/Getting-Started/Installation/
- https://launchpad.net/~cppiber/+archive/ubuntu/hyprland
- https://github.com/cpiber/hyprland-ppa
- https://github.com/nwg-piotr/nwg-hello
- https://github.com/nwg-piotr/nwg-hello/blob/main/LICENSE
- https://github.com/labwc/labwc/tree/0.9.3
- https://github.com/eylles/pywal16
- https://sw.kovidgoyal.net/kitty/conf/

The terminal-first runtime uses Ghostty, Yazi, Superfile, Wiremix and Bluetui.
Their binary/source inputs retain their upstream licensing; they are not covered
by the project's MIT grant. The recovery kit preserves the original downloaded
tool archives and Wiremix registry source crates, including their supplied
notices. The generated vendor checksum files are integrity metadata. Review the
licences and source obligations of these inputs before distributing a binary kit.
tmux, btop, BlueZ and preview/build tools are ordinary Ubuntu packages with their
package-provided upstream notices.

- https://github.com/ghostty-org/ghostty
- https://github.com/sxyazi/yazi
- https://github.com/yorukot/superfile
- https://github.com/tsowell/wiremix
- https://github.com/pythops/bluetui
- https://github.com/tmux/tmux
- https://github.com/aristocratos/btop

The optional file-manager appearance setup retains Superfile v1.6.0's default
configuration and Catppuccin Mocha theme as fresh-install fallback data. Existing
themes supply their own syntax/semantic palette when adapted. Source comments
and attribution are preserved; the Superfile MIT notice is included at
[LICENSES/superfile.txt](LICENSES/superfile.txt) and copied to the user's data tree.
Yazi's appearance uses small original overrides; its full icon/file-type tables
remain supplied by the installed program.

The opt-in shared Bash appearance add-on pins Oh My Posh (MIT), JetBrains Mono
Nerd Font (OFL-1.1) and ble.sh (BSD-3-Clause) in `locks/terminal-amd64.json`.
The Oh My Posh notice is retained in `LICENSES/oh-my-posh.txt`; font and ble.sh
archives retain their supplied licences during installation. These inputs are
separate from the base recovery kit's SPDX inventory. No third-party binaries
or font archives are committed to Git.

- https://github.com/JanDeDobbeleer/oh-my-posh
- https://github.com/ryanoasis/nerd-fonts
- https://github.com/akinomyoga/ble.sh

The bundled PPA key is public, fingerprint
A54D23B62FF3FCC76EFF71E8FDBAAA1CF0CCF48E. It is scoped with Signed-By;
no apt-key, insecure download option or anonymous root installer is used.
