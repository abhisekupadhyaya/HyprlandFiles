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

For a styling update that preserves your current font, size and line height,
and does not download or replace any fonts or tools:

```sh
python3 tools/terminal_setup.py apply --style-only
```

Oh My Posh uses one compact row of navy/blue context ribbons above a fixed `❯`
input marker, joined by a subtle blue `╭─` / `╰─` connector. A leading blank line
separates the previous command's output from the next prompt; each command keeps
its context header in scrollback. It shows `user@host`, project/folder, Git branch
and changed/staged indicators. Long paths and branch names are abbreviated;
less essential fields hide in narrow terminals. The input marker turns red on
failure, with the exit code beside the context. Duration appears only above two
seconds. Constant RAM, shell and clock labels are omitted to keep the command
area clear. Existing font preferences remain unchanged with `--style-only`.

Active Python virtualenv, Conda, explicit pyenv and direnv contexts appear only
when their activation variables are present. Generic `.venv`/`venv` names use
their parent directory; custom names are retained. A virtualenv takes priority
over a surrounding Conda environment. Node projects get a Node badge, including
the selected NVM version when `NVM_BIN` identifies it. These badges do not launch
Python, Conda, pyenv, Node or npm, read `.env` secrets, or activate environments.
With a different Node manager, the badge says `node` rather than probing for a
version. Ordinary activation/deactivation updates the next prompt. The shared
Bash hook suppresses duplicate activation prefixes with
`VIRTUAL_ENV_DISABLE_PROMPT=1` and `CONDA_CHANGEPS1=false`.

ble.sh supplies Bash history suggestions and syntax highlighting; Right Arrow
accepts suggestions. Optional history compaction collapses previous prompts
while staying in the same directory and activation context. The first full
header after a directory/environment change remains as a scrollback landmark.
Compaction reuses ble.sh's rendered prompt without another prompt process, and
removes the leading gap together with the header.

The palette source is `config/terminal/blue-oled.json`: an 80% black tint,
off-white text, blue/cyan accents and coordinated ANSI colours. The Ghostty
overlay loads after the cached wallpaper palette. Prompt cells keep opaque
backgrounds so ribbon labels stay sharp. A separate optional Hyprland appearance
include enables stronger cached blur, subtle grain and vibrancy. It preserves
personal appearance settings and does not touch `hypr/user.lua` or dim the whole
window/text with an opacity rule. Ghostty's native blur option also works on
supported platforms; under Hyprland, the compositor supplies the blur.
For an already running Hyprland session, apply the include with
`hyprctl reload config-only`; this does not restart the compositor.

VS Code keeps black editor/terminal/panel surfaces with blue accents. Its native
Modern UI glass controls enable frosted menus and overlays in supported desktop
versions. These are application-scoped settings: Remote SSH cannot configure
the separate client's application preferences. Merge the three keys from
`~/.config/hyprlandfiles/terminal/vscode-glass.settings.json` into the **local
User Settings JSON** on the computer displaying VS Code. This controls supported
menus/overlays; it does not turn VS Code's terminal canvas into an OS-transparent
window. OS/VS Code reduced-transparency preferences are respected.

Actual black levels, HDR brightness and wide-gamut performance depend on the
display hardware and colour management; the theme does not change calibration.

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
HF_PROMPT_TRANSIENT=1 bash
```

The last option enables compact history; full spaced headers are the default.

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
