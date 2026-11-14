import io
import contextlib
import json
import os
from pathlib import Path
import pty
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import jsonc
import terminal_setup as terminal

ROOT=Path(__file__).resolve().parents[1]


class Settings(unittest.TestCase):
    def test_jsonc_nested_merge_preserves_comments_strings_and_other_profiles(self):
        original='''{
  // keep my preferences
  "editor.fontSize": 18,
  "url": "https://example.test/a/*b*/",
  "workbench.colorCustomizations": {
    "editor.background": "#ffffff", // replace only this value
    "custom.color": "#123456",
  },
  "terminal.integrated.profiles.linux": {"personal": {"path": "/bin/sh"}},
}
'''
        updates={'workbench.colorCustomizations':{'editor.background':'#000000','terminal.background':'#000000'},
                 'terminal.integrated.profiles.linux':{'Bash':{'path':'/bin/bash'}},'new.setting':True}
        merged=jsonc.merge(original,updates);value=jsonc.parse(merged).value
        self.assertIn('// keep my preferences',merged)
        self.assertIn('// replace only this value',merged)
        self.assertIn('"editor.fontSize": 18',merged)
        self.assertEqual(value['url'],'https://example.test/a/*b*/')
        self.assertEqual(value['workbench.colorCustomizations']['custom.color'],'#123456')
        self.assertEqual(value['terminal.integrated.profiles.linux']['personal']['path'],'/bin/sh')
        self.assertEqual(jsonc.merge(merged,updates),merged)

    def test_invalid_or_duplicate_settings_are_refused(self):
        for value in ('{"a":1,"a":2}','{/* unclosed','[]','{"a":NaN}', '{"a": 1} trailing'):
            with self.subTest(value=value),self.assertRaises(ValueError):jsonc.merge(value,{'b':1})

    def test_bash_hook_preserves_customizations_and_updates_once(self):
        original='export MY_CUSTOM_PATH="unchanged"\n# NVM stays here\n'
        first=terminal.managed_block(original,'source "new-file"')
        second=terminal.managed_block(first,'source "updated-file"')
        self.assertTrue(second.startswith(original))
        self.assertEqual(second.count(terminal.BEGIN),1)
        self.assertNotIn('source "new-file"',second)
        self.assertIn('source "updated-file"',second)
        with self.assertRaises(ValueError):terminal.managed_block(terminal.BEGIN,'bad')

    def test_local_and_remote_code_preferences_keep_private_modes_and_unrelated_keys(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d)
            targets=[home/'.config/Code/User/settings.json',home/'.vscode-server/data/Machine/settings.json']
            for target in targets:
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text('// private\n{"editor.fontSize":18,}\n');target.chmod(0o600)
            ops=terminal.configuration_operations(ROOT,home)
            for target in targets:
                op=next(op for op in ops if op['path']==str(target))
                value=jsonc.parse(op['data']).value
                self.assertEqual(op['mode'],0o600)
                self.assertEqual(value['editor.fontSize'],18)
                self.assertEqual(value['terminal.integrated.profiles.linux']['Bash (HyprlandFiles)']['path'],'/bin/bash')
                for key in ('editor.background','terminal.background','panel.background'):
                    self.assertEqual(value['workbench.colorCustomizations'][key],'#000000')

    def test_symlinked_personal_settings_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);original=home/'original';original.write_text('untouched')
            (home/'.bashrc').symlink_to(original)
            with self.assertRaises(ValueError):terminal.configuration_operations(ROOT,home)
            self.assertEqual(original.read_text(),'untouched')

    def test_glass_hook_preserves_custom_lua_and_application_settings_stay_local(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);appearance=home/'.config/hypr/appearance.lua';appearance.parent.mkdir(parents=True)
            original='-- personal appearance comment\nhl.config({ general = { border_size = 3 } })\n'
            appearance.write_text(original);appearance.chmod(0o600)
            user=appearance.with_name('user.lua');user.write_text('-- never replace this')
            (home/'.vscode-server').mkdir()
            ops=terminal.configuration_operations(ROOT,home)
            glass=next(op for op in ops if op['path']==str(appearance))
            self.assertTrue(glass['data'].startswith(original));self.assertEqual(glass['mode'],0o600)
            self.assertFalse(any(op['path']==str(user) for op in ops))
            appearance.write_text(glass['data'])
            again=next(op for op in terminal.configuration_operations(ROOT,home) if op['path']==str(appearance))
            self.assertEqual(again['data'],glass['data'])
            for remote in (False,True):
                target=home/('.vscode-server/data/Machine/settings.json' if remote else '.config/Code/User/settings.json')
                settings=jsonc.parse(next(op['data'] for op in ops if op['path']==str(target))).value
                self.assertEqual('workbench.modernUIFrostedGlass' in settings,not remote)

    def test_style_only_preserves_existing_font_and_size(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);overlay=home/'.config/hyprlandfiles/terminal/ghostty.conf';overlay.parent.mkdir(parents=True)
            overlay.write_text('font-family = ""\nfont-family = Personal Font\nfont-size = 17\nadjust-cell-height = 8%\nbackground-opacity = 1\n')
            code=home/'.config/Code/User/settings.json';code.parent.mkdir(parents=True)
            code.write_text('{"terminal.integrated.fontFamily":"Personal Font","terminal.integrated.fontSize":19}')
            ops=terminal.configuration_operations(ROOT,home,preserve_typography=True)
            ghostty=next(op['data'] for op in ops if op['path']==str(overlay))
            self.assertIn('font-family = Personal Font\n',ghostty)
            self.assertIn('font-size = 17\n',ghostty)
            self.assertIn('adjust-cell-height = 8%\n',ghostty)
            settings=jsonc.parse(next(op['data'] for op in ops if op['path']==str(code))).value
            self.assertEqual(settings['terminal.integrated.fontFamily'],'Personal Font')
            self.assertEqual(settings['terminal.integrated.fontSize'],19)

    def test_ribbon_text_has_readable_contrast_on_opaque_segment_backgrounds(self):
        palette=json.loads((ROOT/'config/terminal/blue-oled.json').read_text())
        def luminance(color):
            values=[int(color[i:i+2],16)/255 for i in (1,3,5)]
            linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
            return sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))
        for block in terminal.prompt(palette)['blocks']:
            for segment in block['segments']:
                if segment['background']=='transparent':continue
                a,b=sorted(map(luminance,(segment['foreground'],segment['background'])))
                self.assertGreaterEqual((b+.05)/(a+.05),4.5,segment['type'])

    def test_style_only_does_not_download_or_replace_fonts_or_programs(self):
        with tempfile.TemporaryDirectory() as d,patch.object(terminal,'Transaction'), \
                patch.object(terminal,'configuration_operations',return_value=[]), \
                patch.object(terminal,'assets') as download,patch.object(terminal,'payload_operations') as payload, \
                patch.object(terminal.subprocess,'run') as run,contextlib.redirect_stdout(io.StringIO()):
            terminal.apply(ROOT,Path(d),Path(d)/'cache',style_only=True)
            download.assert_not_called();payload.assert_not_called()
            self.assertFalse(any(call.args[0][0]=='fc-cache' for call in run.call_args_list))

    def test_font_or_suggestion_archive_cannot_write_links_or_parent_paths(self):
        for name,kind in (('../outside',tarfile.REGTYPE),('symlink',tarfile.SYMTYPE)):
            with self.subTest(name=name):
                data=io.BytesIO()
                with tarfile.open(fileobj=data,mode='w') as archive:
                    item=tarfile.TarInfo(name);item.type=kind;item.linkname='/etc/passwd'
                    archive.addfile(item)
                data.seek(0)
                with tarfile.open(fileobj=data) as archive,self.assertRaises(ValueError):terminal.safe_members(archive)


class Bash(unittest.TestCase):
    def test_noninteractive_shell_does_not_initialize_prompt_or_change_term(self):
        script='PS1=plain; source "$1"; printf "TERM=%s\nPS1=%s\n" "$TERM" "$PS1"'
        result=subprocess.run(['/bin/bash','--noprofile','--norc','-c',script,'test',str(ROOT/'config/bash/terminal.bash')],
            env=dict(os.environ,TERM='dumb',PS1='plain'),capture_output=True,text=True,check=True)
        self.assertEqual(result.stdout,'TERM=dumb\nPS1=plain\n')
        self.assertEqual(result.stderr,'')

    def test_interactive_initialization_runs_once_and_keeps_existing_prompt_hooks(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);binary=home/'.local/bin/oh-my-posh';binary.parent.mkdir(parents=True)
            binary.write_text('#!/bin/sh\nprintf "%s\\n" "(( HF_PROMPT_INIT_COUNT += 1 ))"\n');binary.chmod(0o755)
            config=home/'.config/hyprlandfiles/terminal/blue-oled.omp.json';config.parent.mkdir(parents=True);config.write_text('{}')
            env=dict(os.environ,HOME=str(home),TERM='xterm-256color',HF_BASH_SUGGESTIONS='0',HF_BASH_STYLE='blue-oled')
            env.pop('_HF_BASH_INITIALIZED',None)
            master,slave=pty.openpty()
            script='PROMPT_COMMAND=existing_hook; source "$1"; source "$1"; printf "count:%s TERM:%s hook:%s\\n" "$HF_PROMPT_INIT_COUNT" "$TERM" "$PROMPT_COMMAND"'
            try:
                result=subprocess.run(['/bin/bash','--noprofile','--norc','-ic',script,'test',str(ROOT/'config/bash/terminal.bash')],
                    env=env,stdin=slave,stdout=slave,stderr=slave,timeout=8)
                os.close(slave);slave=None;output=b''
                while True:
                    try:part=os.read(master,65536)
                    except OSError:break
                    if not part:break
                    output+=part
                self.assertEqual(result.returncode,0)
                self.assertIn(b'count:1 TERM:xterm-256color hook:existing_hook',output)
            finally:
                os.close(master)
                if slave is not None:os.close(slave)


if __name__=='__main__':unittest.main()
