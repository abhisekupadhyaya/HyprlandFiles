# Shared by interactive Bash in Ghostty, VS Code, SSH and tmux.
# Existing aliases, completion, PATH and shell integration remain in ~/.bashrc.
[[ $- == *i* && -t 0 && -t 1 ]] || return 0
[[ ${TERM:-dumb} != dumb && ${TERM:-} != linux ]] || return 0
[[ ${HF_BASH_STYLE:-blue-oled} != plain ]] || return 0
[[ ${_HF_BASH_INITIALIZED:-0} != 1 ]] || return 0
[[ -x "$HOME/.local/bin/oh-my-posh" ]] || return 0
[[ -r "$HOME/.config/hyprlandfiles/terminal/blue-oled.omp.json" ]] || return 0
_HF_BASH_INITIALIZED=1

# Loading with deferred attachment lets the prompt initialize before the editor.
if [[ ${HF_BASH_SUGGESTIONS:-1} != 0 && ! ${BLE_VERSION:-} &&
      -r "$HOME/.local/share/hyprlandfiles/ble/ble.sh" ]]; then
    source "$HOME/.local/share/hyprlandfiles/ble/ble.sh" --attach=none
fi

# Native terminal OSC hooks are owned by Ghostty/VS Code. Do not override TERM,
# auto-attach tmux, or initialize a second terminal-integration protocol here.
eval "$("$HOME/.local/bin/oh-my-posh" init bash --config "$HOME/.config/hyprlandfiles/terminal/blue-oled.omp.json")"

if [[ ${BLE_VERSION:-} ]]; then
    bleopt complete_auto_complete=1
    bleopt prompt_eol_mark='%'
    ble-face -s auto_complete fg='#93A4BB'
    ble-attach
fi
