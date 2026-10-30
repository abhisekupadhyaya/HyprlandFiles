-- HyprlandFiles: Hyprland 0.57.0. Based on the verified local bare config.
-- LeyzS-inspired styling is isolated in appearance.lua; hardware/lid policy here.

------------------------------------------------------------------ monitors
-- Automatic EDID scaling; installer can render an explicit scale override.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = @SCALE_LUA@ })

------------------------------------------------------------------ programs
local terminal = "kitty"
local launcher = "fuzzel"
local files    = "thunar"
local lock     = "/usr/local/bin/hf-lock"

------------------------------------------------------------------ environment
hl.env("XCURSOR_SIZE", "24")
hl.env("HYPRCURSOR_SIZE", "24")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")

------------------------------------------------------------------ core options
hl.config({
    ecosystem = {
        no_update_news      = true,
        no_donation_nag     = true,
        -- Screen capture, virtual keyboards and plugins need an explicit allow.
        enforce_permissions = true,
    },
    misc = {
        disable_hyprland_logo      = true,
        disable_splash_rendering   = true,
        force_default_wallpaper    = 0,
        -- Lets a fresh hyprlock take over if the locker crashes; the session
        -- stays locked in the meantime (red "lockdead" screen).
        allow_session_lock_restore = true,
    },
    general = {
        gaps_in     = 4,
        gaps_out    = 8,
        border_size = 2,
        layout      = "dwindle",
    },
    decoration = {
        rounding = 8,
        blur     = { enabled = false },   -- measured and enabled in Stage 4/5
        shadow   = { enabled = false },
    },
    animations = { enabled = true },
    dwindle    = { preserve_split = true },
    input = {
        kb_layout    = "@KEYBOARD@",
        follow_mouse = 1,
        natural_scroll = true,
        touchpad = {
            natural_scroll       = true,
            tap_to_click         = true,
            disable_while_typing = true,
        },
    },
})

------------------------------------------------------------------ permissions
hl.permission({ binary = "/usr/bin/grim",                           type = "screencopy", mode = "allow" })
hl.permission({ binary = "/usr/libexec/xdg-desktop-portal-hyprland", type = "screencopy", mode = "allow" })
hl.permission({ binary = ".*",                                      type = "plugin",     mode = "deny"  })

------------------------------------------------------------------ session start
hl.on("hyprland.start", function()
    -- hf-lock (run from hypridle, a user service) finds this session by id.
    hl.exec_cmd("systemctl --user import-environment XDG_SESSION_ID")
    -- polkit accepts an agent only from inside the session it serves, so the
    -- agent runs in this session's scope, not as a user service.
    hl.exec_cmd("systemd-cat -t hyprpolkitagent /usr/local/bin/hf-polkit")
    -- A session can finish PAM while the lid is being closed. Check startup
    -- state too; the switch bind alone only handles later events.
    hl.exec_cmd("/usr/local/bin/hf-panel startup")
end)

-- v0.57 emits this event synchronously before stopping the compositor. These
-- affected packaged clients otherwise fail on Wayland disconnection before the
-- native asynchronous graphical-session teardown reaches them. Stop their
-- native units first, only when the desktop is actually exiting. No app-kill,
-- failure-reset or SuccessExitStatus exception is used. Timeout bounds the
-- wait for systemd; failures remain visible for diagnosis.
hl.on("hyprland.shutdown", function()
    local worker = io.popen("/usr/bin/python3 /usr/local/bin/hf-session-stop", "r")
    if not worker then error("HyprlandFiles: could not start desktop helper shutdown") end
    local result = worker:read("*a")
    worker:close()
    if result ~= "OK\n" then
        io.stderr:write("HyprlandFiles: desktop helper shutdown did not confirm success: " .. tostring(result) .. "\n")
    end
end)

------------------------------------------------------------------ lid
-- logind ignores the lid (HandleLidSwitch=ignore); Hyprland owns it here.
-- The root lifecycle controller also asks logind to lock as a backstop.
local function panel(action)
    hl.timer(function()
        hl.exec_cmd("/usr/local/bin/hf-panel " .. action)
    end, { timeout = 500, type = "oneshot" })
end
-- Installed only for the optional laptop/server profile.
if @LID_ENABLED@ then
    hl.bind("switch:on:Lid Switch", function()
        hl.exec_cmd(lock)
        panel("close")
    end, { locked = true, description = "Lid closed: lock and turn internal panels off" })
    hl.bind("switch:off:Lid Switch", function()
        panel("resume")
    end, { locked = true, description = "Lid opened: display on; session remains locked" })
end

------------------------------------------------------------------ keybinds
local register_bindings = dofile("@HOME@/.config/hypr/bindings.lua")
register_bindings({ terminal = terminal, launcher = launcher, files = files, lock = lock })

------------------------------------------------------------------ rules
hl.window_rule({
    name  = "suppress-maximize-events",
    match = { class = ".*" },
    suppress_event = "maximize",
})

-- Base settings are usable independently; only require appearance after the
-- default and bare Lua configs have both been verified on this release.
local root = "@HOME@/.config/hypr/"
dofile(root .. "appearance.lua")

-- Keep local customizations separate; this file is never replaced by the installer.
local user = os.getenv("HOME") .. "/.config/hypr/user.lua"
local f = io.open(user, "r")
if f then f:close(); dofile(user) end
