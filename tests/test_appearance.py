import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import appearance

ROOT=Path(__file__).resolve().parents[1]

class Files(unittest.TestCase):
    def test_ini_merge_preserves_other_keys_sections_and_comments(self):
        text='# personal\n[Settings]\ngtk-theme-name=Light\ngtk-font-name=My Font 12\n[Other]\ncustom=yes\n'
        merged=appearance.merge_settings(text,{'gtk-theme-name':'Adwaita-dark','gtk-application-prefer-dark-theme':'1'})
        self.assertIn('# personal\n',merged)
        self.assertIn('gtk-font-name=My Font 12\n',merged)
        self.assertIn('[Other]\ncustom=yes\n',merged)
        self.assertIn('gtk-theme-name=Adwaita-dark\n',merged)
        self.assertEqual(appearance.merge_settings(merged,{'gtk-theme-name':'Adwaita-dark','gtk-application-prefer-dark-theme':'1'}),merged)

    def test_vscode_custom_jsonc_is_preserved_and_fresh_defaults_seeded(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);code=home/'.config/Code/User/settings.json'
            ops=appearance.file_operations(ROOT,home)
            fresh=next(x for x in ops if x['path']==str(code))
            self.assertTrue(json.loads(fresh['data'])['window.autoDetectColorScheme'])
            code.parent.mkdir(parents=True);code.write_text('// private custom settings\n{"editor.fontSize":16,}\n')
            self.assertFalse(any(x['path']==str(code) for x in appearance.file_operations(ROOT,home)))

    def test_missing_settings_section_is_added_without_losing_existing_data(self):
        merged=appearance.merge_settings('[Other]\na=1\n',{'gtk-application-prefer-dark-theme':'1'})
        self.assertEqual(merged,'[Other]\na=1\n[Settings]\ngtk-application-prefer-dark-theme=1\n')

    def test_vscode_theme_names_are_detected_not_assumed(self):
        with tempfile.TemporaryDirectory() as d:
            themes=Path(d)/'package.json'
            template='{"window.autoDetectColorScheme":true}'
            self.assertNotIn('workbench.colorTheme',json.loads(appearance.code_defaults(template,themes)))
            for theme in ('Dark Modern','Default Dark Modern','Future Dark'):
                themes.write_text(json.dumps({'contributes':{'themes':[{'id':theme,'uiTheme':'vs-dark'}]}}))
                self.assertEqual(json.loads(appearance.code_defaults(template,themes))['workbench.colorTheme'],theme)

try:
    from gi.repository import Gio
except ImportError:
    Gio=None

@unittest.skipIf(Gio is None,'Native Gio is available on Ubuntu target; optional in generic CI')
class Preferences(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)
        self.settings=Gio.Settings.new_with_backend(appearance.SCHEMA,Gio.memory_settings_backend_new())
        self.backend=patch.object(appearance,'settings_backend',return_value=self.settings)
        self.backend.start();self.addCleanup(self.backend.stop)

    def test_snapshot_restores_unset_keys_and_preserves_unrelated_preferences(self):
        self.settings.set_string('font-name','Unrelated Font 12')
        self.assertIsNone(self.settings.get_user_value('color-scheme'))
        snapshot=appearance.apply_preferences(self.home)
        self.assertEqual(self.settings.get_string('color-scheme'),'prefer-dark')
        appearance.rollback(self.home,snapshot)
        self.assertIsNone(self.settings.get_user_value('color-scheme'))
        self.assertIsNone(self.settings.get_user_value('gtk-theme'))
        self.assertEqual(self.settings.get_string('font-name'),'Unrelated Font 12')

    def test_later_preference_edit_blocks_rollback(self):
        snapshot=appearance.apply_preferences(self.home)
        self.settings.set_string('color-scheme','prefer-light')
        with self.assertRaises(ValueError):appearance.rollback(self.home,snapshot)
        self.assertEqual(self.settings.get_string('color-scheme'),'prefer-light')
