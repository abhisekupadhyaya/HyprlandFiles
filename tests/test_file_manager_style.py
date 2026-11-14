import json
from pathlib import Path
import tempfile
import tomllib
import unittest

import file_manager_style as style

ROOT=Path(__file__).resolve().parents[1]
PALETTE=json.loads((ROOT/'config/terminal/blue-oled.json').read_text())


class PreservingAppearance(unittest.TestCase):
    def test_toml_comments_custom_styles_arrays_and_root_sections_survive(self):
        original='''# personal settings
theme = 'old'  # selected theme
transparent_background = false
editor = 'nvim'
[indicator]
current = { fg = "#ffbc03", underline = true } # preserve label colour
[filetype]
rules = [
  { mime = "**/image/*", fg = "#fabc12" },
]
[open_with]
theme = "unrelated command"
'''
        changes={'':{'theme':'blue','transparent_background':True},
                 'indicator':{'current':{'bg':'#17375E','reversed':False}}}
        updated=style.merge(original,changes);before=tomllib.loads(original);after=tomllib.loads(updated)
        for key in ('editor','filetype','open_with'):self.assertEqual(before[key],after[key])
        self.assertEqual(after['indicator']['current']['fg'],'#ffbc03')
        self.assertTrue(after['indicator']['current']['underline'])
        self.assertIn('# selected theme',updated);self.assertIn('# preserve label colour',updated)
        self.assertEqual(style.merge(updated,changes),updated)
        with self.assertRaises(ValueError):style.merge('theme = [\n"old"\n]\n',{'':{'theme':'new'}})

    def test_personal_file_colours_syntax_hotkeys_and_private_modes_survive(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);yazi=home/'.config/yazi/theme.toml';yazi.parent.mkdir(parents=True)
            yazi.write_text('[filetype]\nrules = [{ url = "*.py", fg = "#abcdef" }]\n'
                '[icon]\nexts = [{ name = "py", fg = "#fedcba", text = "P" }]\n'
                '[mgr]\nsyntect_theme = "personal.tmTheme"\n');yazi.chmod(0o600)
            config=home/'.config/superfile/config.toml';config.parent.mkdir(parents=True)
            config.write_text('theme = "personal"\neditor = "nvim"\nsidebar_width = 12\n[open_with]\npy = "code"\n');config.chmod(0o600)
            theme=config.parent/'theme/personal.toml';theme.parent.mkdir()
            theme.write_text((ROOT/'config/superfile/theme/hyprland-blue-glass.toml').read_text()
                .replace('"catppuccin-mocha"','"dracula"').replace('correct = "#a6e3a1"','correct = "#123456"'))
            hotkeys=config.with_name('hotkeys.toml');hotkeys.write_text('quit = ["q"]\n')
            ops=style.configuration_operations(ROOT,home,PALETTE)
            by_path={op['path']:op for op in ops}
            for path in (yazi,config):self.assertEqual(by_path[str(path)]['mode'],0o600)
            result=tomllib.loads(by_path[str(yazi)]['data']);original=tomllib.loads(yazi.read_text())
            for key in ('filetype','icon'):self.assertEqual(result[key],original[key])
            self.assertEqual(result['mgr']['syntect_theme'],'personal.tmTheme')
            result=tomllib.loads(by_path[str(config.parent/'theme/hyprland-blue-glass.toml')]['data'])
            self.assertEqual(result['code_syntax_highlight'],'dracula');self.assertEqual(result['correct'],'#123456')
            original=tomllib.loads(theme.read_text())
            for key in ('gradient_color','error','cancel','modal_cancel_bg','help_menu_title'):
                self.assertEqual(result[key],original[key])
            result=tomllib.loads(by_path[str(config)]['data'])
            self.assertEqual(result['editor'],'nvim');self.assertEqual(result['sidebar_width'],12)
            self.assertEqual(result['open_with'],{'py':'code'});self.assertTrue(result['transparent_background'])
            self.assertNotIn(str(hotkeys),by_path);self.assertNotIn(str(theme),by_path)

    def test_configuration_and_active_theme_symlinks_are_refused_before_writes(self):
        for target in ('yazi/theme.toml','superfile/theme/catppuccin-mocha.toml','superfile/theme/hyprland-blue-glass.toml'):
            with self.subTest(target=target),tempfile.TemporaryDirectory() as d:
                home=Path(d);other=home/'original';other.write_text('untouched')
                path=home/'.config'/target;path.parent.mkdir(parents=True);path.symlink_to(other)
                with self.assertRaises(ValueError):style.configuration_operations(ROOT,home,PALETTE)
                self.assertEqual(other.read_text(),'untouched')
