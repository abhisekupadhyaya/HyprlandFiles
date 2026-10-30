-- Selective LeyzS seed: 10px corners, accent outlines, one coordinated curve.
-- No perpetual border animation, heavy blur, screen shader or video wallpaper.
hl.config({
 general = { gaps_in = 4, gaps_out = 8, border_size = 2, resize_on_border = true },
 decoration = {
  rounding = 10,
  blur = { enabled = true, size = 3, passes = 1 },
  shadow = { enabled = true, range = 6, render_power = 3 },
 },
 misc = { force_default_wallpaper = 0 },
 debug = { vfr = true },
})
hl.curve("hf", { type = "bezier", points = { {0.2, 0.9}, {0.3, 1.0} } })
hl.animation({ leaf = "global", enabled = true, speed = 1.6, bezier = "hf" })
hl.animation({ leaf = "windows", enabled = true, speed = 1.6, bezier = "hf", style = "popin 96%" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 1.6, bezier = "hf", style = "fade" })
local colors = os.getenv("HOME") .. "/.local/state/hyprlandfiles/current/hyprland.lua"
local file = io.open(colors, "r")
if file then file:close(); dofile(colors) end
