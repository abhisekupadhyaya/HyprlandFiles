-- Super is Command. Inspired by Mac conventions and Omarchy's documented
-- native send-key-state approach; no virtual input device or remapping daemon.
return function(programs)
    local root = "/usr/local/bin/"
    local function bind(keys, action, description, options)
        local opts = {}
        for k, v in pairs(options or {}) do opts[k] = v end
        opts.description = description
        hl.bind(keys, action, opts)
    end
    local function run(command) return hl.dsp.exec_cmd(command) end
    local function terminal_focused()
        local w = hl.get_active_window()
        return w and (w.class or ""):lower() == "kitty"
    end
    local function chord(mods, key)
        -- Separate down/up avoids stuck synthetic modifiers on this release.
        hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = key, state = "down" }))
        hl.timer(function()
            hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = key, state = "up" }))
        end, { timeout = 50, type = "oneshot" })
    end
    local function app_shortcut(key, description, terminal_mods, terminal_key, gui_mods)
        bind("SUPER + " .. key, function()
            if terminal_focused() then
                -- Never turn Command+C/S/Z into interrupt, XOFF or job control.
                if terminal_mods then chord(terminal_mods, terminal_key or key) end
            else
                chord(gui_mods or "CTRL", key)
            end
        end, description)
    end

    bind("SUPER + Space", run(programs.launcher), "Search applications — Command+Space")
    bind("SUPER + D", run(programs.launcher), "Search applications (alias)")
    bind("SUPER + CTRL + Space", run(root .. "hf-menu main"), "HyprlandFiles command menu")
    bind("SUPER + K", run(root .. "hf-menu help"), "Shortcut and recovery guide")
    bind("SUPER + slash", run(root .. "hf-menu help"), "Shortcut and recovery guide (alias)")
    bind("SUPER + Return", run(programs.terminal), "Terminal")
    bind("SUPER + E", run(programs.files), "File manager")
    bind("SUPER + ALT + Space", run(programs.files), "File manager — Command+Option+Space")

    app_shortcut("C", "Copy — terminal uses Ctrl+Shift+C", "CTRL SHIFT")
    app_shortcut("V", "Paste — terminal uses Ctrl+Shift+V", "CTRL SHIFT")
    app_shortcut("W", "Close tab/window — application handles unsaved work", "CTRL SHIFT")
    app_shortcut("T", "New tab", "CTRL SHIFT")
    app_shortcut("N", "New window", "CTRL SHIFT")
    app_shortcut("F", "Find; in Kitty, open searchable scrollback", "CTRL SHIFT", "H")
    app_shortcut("A", "Select all in applications")
    app_shortcut("X", "Cut in applications")
    app_shortcut("S", "Save in applications")
    app_shortcut("Z", "Undo in applications")
    app_shortcut("L", "Location/address field in applications")
    bind("SUPER + SHIFT + Z", function()
        if not terminal_focused() then chord("CTRL SHIFT", "Z") end
    end, "Redo in applications")
    bind("SUPER + Q", hl.dsp.window.close(), "Gracefully close focused application window")

    bind("SUPER + CTRL + Q", run(programs.lock), "Lock — Control+Command+Q")
    bind("SUPER + CTRL + L", run(programs.lock), "Lock (Omarchy-style alias)")
    bind("SUPER + Escape", run(root .. "hf-menu power"), "Session and power menu (confirmation)")
    bind("SUPER + SHIFT + E", run(root .. "hf-menu power"), "Session and power menu (alias)")
    bind("SUPER + ALT + W", run(root .. "hf-menu wallpaper"), "Wallpaper and generated colours")
    bind("SUPER + ALT + N", run("swaync-client -t"), "Notifications")
    bind("SUPER + CTRL + F", hl.dsp.window.fullscreen(), "Fullscreen — Control+Command+F")
    bind("SUPER + ALT + T", hl.dsp.window.float({ action = "toggle" }), "Toggle floating/tiling")
    bind("SUPER + J", hl.dsp.layout("togglesplit"), "Toggle tile split")
    bind("SUPER + Tab", hl.dsp.window.cycle_next(), "Next window on workspace")
    bind("SUPER + SHIFT + Tab", hl.dsp.window.cycle_next({ next = false }), "Previous window on workspace")
    bind("ALT + Tab", hl.dsp.window.cycle_next(), "Next window (Linux alias)")
    bind("ALT + SHIFT + Tab", hl.dsp.window.cycle_next({ next = false }), "Previous window (Linux alias)")
    bind("CTRL + left", hl.dsp.focus({ workspace = "e-1" }), "Previous workspace — Mac Spaces")
    bind("CTRL + right", hl.dsp.focus({ workspace = "e+1" }), "Next workspace — Mac Spaces")
    bind("ALT + left", function() chord("CTRL", "left") end, "Previous word — Option+Left")
    bind("ALT + right", function() chord("CTRL", "right") end, "Next word — Option+Right")
    for _, direction in ipairs({"left", "right", "up", "down"}) do
        bind("SUPER + " .. direction, hl.dsp.focus({ direction = direction }), "Focus " .. direction)
    end
    for i = 1, 10 do
        local key = i % 10
        bind("SUPER + " .. key, hl.dsp.focus({ workspace = i }), "Workspace " .. i)
        -- Reserve Command+Shift+3/4 for the familiar Mac screenshots.
        bind("SUPER + CTRL + " .. key, hl.dsp.window.move({ workspace = i }), "Move to workspace " .. i)
    end
    bind("SUPER + mouse:272", hl.dsp.window.drag(), "Move window", { mouse = true })
    bind("SUPER + mouse:273", hl.dsp.window.resize(), "Resize window", { mouse = true })
    bind("Print", run(root .. "hf-screenshot"), "Select screenshot region and copy")
    bind("SUPER + SHIFT + 4", run(root .. "hf-screenshot"), "Select screenshot region — Command+Shift+4")
    bind("SUPER + SHIFT + 3", run(root .. "hf-screenshot full"), "Copy full screenshot — Command+Shift+3")

    local hardware = { locked = true, repeating = true }
    bind("XF86AudioRaiseVolume", run(root .. "hf-control volume up"), "Volume up", hardware)
    bind("XF86AudioLowerVolume", run(root .. "hf-control volume down"), "Volume down", hardware)
    bind("XF86AudioMute", run(root .. "hf-control volume mute"), "Mute", { locked = true })
    bind("XF86AudioMicMute", run("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"), "Microphone mute", { locked = true })
    bind("XF86MonBrightnessUp", run(root .. "hf-control brightness up"), "Brightness up", hardware)
    bind("XF86MonBrightnessDown", run(root .. "hf-control brightness down"), "Brightness down", hardware)
    for key, action in pairs({ XF86AudioPlay = "play-pause", XF86AudioNext = "next", XF86AudioPrev = "previous" }) do
        bind(key, run("playerctl " .. action), "Media: " .. action, { locked = true })
    end
end
