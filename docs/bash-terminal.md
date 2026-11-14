# Shared Bash terminal style

Apply the same Bash prompt and black/blue colours to Ghostty and VS Code:

```sh
python3 tools/terminal_setup.py apply
```

Run as the desktop user, without sudo. This is an explicit appearance add-on;
it can run while the desktop is open and does not restart it. Open a new terminal
after applying. The existing Bash login shell, aliases, NVM, completion, history,
VS Code shell integration and Ghostty shell integration remain in place. No
automatic tmux attachment or TERM override is added.

Oh My Posh displays user/host, a shortened path, Git branch and working/staged
changes, commands taking over two seconds and nonzero exit status. A blue input
marker starts the second line. Labels use ordinary text, so the prompt remains
readable in Remote SSH clients without Nerd Font glyphs. ble.sh supplies Bash
history suggestions and syntax highlighting; Right Arrow accepts suggestions.

The palette source is `config/terminal/blue-oled.json`: opaque `#000000`,
off-white text, blue/cyan accents and coordinated ANSI colours. The Ghostty
overlay loads after the cached wallpaper palette. VS Code uses Dark Modern as
its syntax base with black editor/terminal/panel surfaces and blue accents.
This creates an OLED-style appearance; actual black levels, HDR brightness and
wide-gamut performance depend on display hardware and colour management.

Four JetBrains Mono Nerd Font Mono styles are installed per user. VS Code's
terminal font has standard monospace fallbacks. In a Remote SSH window, Bash and
the prompt run on the server, while fonts are rendered on the client. Install
the same font on that client for identical typography. Its four TTF files and
OFL licence are in `~/.local/share/fonts/hyprlandfiles/`. A portable VS Code
settings export is at `~/.config/hyprlandfiles/terminal/vscode-settings.json`.

The add-on merges targeted settings into local VS Code preferences and, when
present, `.vscode-server/data/Machine/settings.json`. JSONC comments, unrelated
settings/profiles and existing permissions are preserved. A labelled block in
`.bashrc` loads `~/.config/hyprlandfiles/terminal/terminal.bash` for interactive
TTY shells. Noninteractive commands and dumb/Linux console terminals retain
ordinary Bash behaviour. Existing configuration symlinks require manual review.

All replacements participate in the existing user backup journal. Keep its
manifests: subsequent installers use them to recognize managed files. The
printed snapshot supports the usual user rollback procedure; save work first
if the main rollback command requires logging out. To temporarily start plain
Bash or disable suggestions without deleting configuration:

```sh
HF_BASH_STYLE=plain bash
HF_BASH_SUGGESTIONS=0 bash
```

Inputs are pinned in `locks/terminal-amd64.json`. Prepare them without applying:

```sh
python3 tools/terminal_setup.py prepare
```

They remain in `.cache/terminal/inputs` and are checked on every run. The initial
download requires network access; applying again from this complete cache does
not. These three add-on inputs are separate from the 36-input base recovery kit
and its SPDX inventory. Retain the add-on cache too for offline reinstallation.

Oh My Posh 32.0.0 and Nerd Fonts 3.5.1 match the release asset SHA256 metadata.
The ble.sh release supplies no asset digest; its pinned hash was computed from
the official versioned `0.4.0-devel3-2` archive. Archive links and unsafe paths
are refused, and supplied font/ble.sh licence files are retained. The Oh My Posh
MIT notice is in `LICENSES/oh-my-posh.txt` and copied into the user's data tree.
