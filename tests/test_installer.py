"""Offline tests: transaction failure modes and a complete disposable install tree."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from hflib import (Transaction, fingerprint, managed_state, operation, require_supported,
                   validate_options, reject_apt_removals, extract_wheel)
import installer

ROOT=Path(__file__).resolve().parents[1]


class Transactions(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.home=self.base/'home';self.home.mkdir()
        self.store=self.base/'private-backups'
        self.tx=Transaction(self.store,self.home)

    def test_backup_permissions_and_exact_rollback(self):
        p=self.home/'existing';p.write_text('original');p.chmod(0o640)
        before=fingerprint(p)
        snapshot=self.tx.apply([operation(p,'changed'),operation(self.home/'new','new')],adopt=True)
        self.assertEqual(self.store.stat().st_mode & 0o777,0o700)
        self.assertEqual((snapshot/'0').stat().st_mode & 0o777,0o640)
        self.tx.rollback(snapshot)
        self.assertEqual(fingerprint(p),before)
        self.assertFalse((self.home/'new').exists())

    def test_all_conflicts_checked_before_any_write(self):
        p=self.home/'unrelated';p.write_text('keep')
        with self.assertRaises(ValueError):
            self.tx.apply([operation(self.home/'new','new'),operation(p,'overwrite')])
        self.assertFalse((self.home/'new').exists());self.assertEqual(p.read_text(),'keep')

    def test_idempotence_and_owned_upgrade(self):
        p=self.home/'config';op=operation(p,'one')
        first=self.tx.apply([op])
        tx=Transaction(self.store,self.home,managed_state(self.store))
        self.assertIsNone(tx.apply([op]))
        second=tx.apply([operation(p,'two')])
        tx.rollback(second);self.assertEqual(p.read_text(),'one')
        tx.rollback(first);self.assertFalse(p.exists())

    def test_rollback_refuses_later_edits_without_partial_restore(self):
        a,b=self.home/'a',self.home/'b'
        snapshot=self.tx.apply([operation(a,'a'),operation(b,'b')])
        a.write_text('personal edit')
        with self.assertRaises(ValueError):self.tx.rollback(snapshot)
        self.assertEqual(b.read_text(),'b')

    def test_dangling_symlink_is_backed_up_and_restored(self):
        p=self.home/'link';p.symlink_to('missing')
        snapshot=self.tx.apply([operation(p,'new')],adopt=True)
        self.tx.rollback(snapshot);self.assertTrue(p.is_symlink());self.assertEqual(os.readlink(p),'missing')

    def test_symlink_directory_escape_and_external_snapshot_refused(self):
        outside=self.base/'outside';outside.mkdir()
        (self.home/'redirect').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):self.tx.apply([operation(self.home/'redirect/file','x')])
        self.assertFalse((outside/'file').exists())
        with self.assertRaises(ValueError):self.tx.rollback(outside)
        with self.assertRaises(ValueError):self.tx.apply([operation(self.home/'../escape','x')])

    def test_interruption_restores_originals_and_blocks_new_apply(self):
        p=self.home/'a';p.write_text('old')
        import hflib
        real=hflib.atomic
        def fail_second_target(path,*args,**kwargs):
            if Path(path)==self.home/'b':raise OSError('simulated disk failure')
            return real(path,*args,**kwargs)
        with patch.object(hflib,'atomic',side_effect=fail_second_target):
            with self.assertRaises(OSError):self.tx.apply([operation(p,'new'),operation(self.home/'b','b')],adopt=True)
        snapshot=next(self.store.iterdir())
        with self.assertRaises(ValueError):managed_state(self.store)
        self.tx.rollback(snapshot)
        self.assertEqual(p.read_text(),'old');self.assertFalse((self.home/'b').exists())

    def test_entire_user_payload_preserves_unrelated_files(self):
        opts=dict(profile='laptop-server',scale='auto',gpu='auto',keyboard='us')
        unrelated=self.home/'.config/hypr/user.lua';unrelated.parent.mkdir(parents=True);unrelated.write_text('-- personal')
        ops=installer.user_operations(ROOT,self.home,opts)
        snapshot=self.tx.apply(ops)
        self.assertIsNone(Transaction(self.store,self.home,managed_state(self.store)).apply(ops))
        lua=(self.home/'.config/hypr/hyprland.lua').read_text()
        self.assertNotIn('@HOME@',lua);self.assertIn('if true then',lua)
        self.tx.rollback(snapshot)
        self.assertEqual(unrelated.read_text(),'-- personal')
        self.assertFalse((self.home/'.config/kitty/kitty.conf').exists())

    def test_entire_system_payload_in_disposable_root(self):
        from types import SimpleNamespace
        account=SimpleNamespace(pw_name='alice')
        with patch.object(installer.pwd,'getpwnam',return_value=SimpleNamespace(pw_name='_greetd')):
            ops=installer.system_operations(ROOT,account,dict(profile='laptop-server',scale='auto',gpu='auto',keyboard='us'))
        for op in ops:op['path']=str(self.home/op['path'].lstrip('/'))
        snapshot=self.tx.apply(ops)
        self.assertTrue((self.home/'etc/greetd/config.toml').is_file())
        self.assertIn('HandleLidSwitch=ignore',(self.home/'etc/systemd/logind.conf.d/90-hyprlandfiles-lid.conf').read_text())
        self.tx.rollback(snapshot)
        self.assertFalse((self.home/'etc/greetd/config.toml').exists())

    def test_preflight_dry_run_does_not_create_backups_or_targets(self):
        result=self.tx.apply([operation(self.home/'new','value')],dry_run=True)
        self.assertEqual(len(result),1)
        self.assertFalse(self.store.exists());self.assertFalse((self.home/'new').exists())


class ActivationSafety(unittest.TestCase):
    def test_user_failure_never_enables_controller(self):
        from types import SimpleNamespace
        a=SimpleNamespace(profile='desktop',scale='auto',gpu='auto',keyboard='us',yes=True,adopt=False)
        with patch.object(installer,'plan'),patch.object(installer,'no_gui'),patch.object(installer,'Transaction'),patch.object(installer,'run') as run,patch.object(installer,'user_install',side_effect=ValueError('user config conflict')):
            with self.assertRaises(ValueError):installer.setup(a)
        self.assertEqual(len(run.call_args_list),1)
        self.assertEqual(run.call_args.args[0][3],'system')

    def test_enable_refuses_incomplete_user_setup(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);home=root/'user';home.mkdir()
            (root/'installed.json').write_text(json.dumps({'user':'alice'}))
            with patch.object(installer,'ROOT_STATE',root),patch.object(installer.os,'geteuid',return_value=0),patch.object(installer,'no_gui'),patch.object(installer.pwd,'getpwnam',return_value=SimpleNamespace(pw_dir=str(home))),patch.object(installer,'run') as run:
                with self.assertRaises(ValueError):installer.enable()
                run.assert_not_called()


class InputSafety(unittest.TestCase):
    def test_unsupported_platforms_fail(self):
        require_supported({'ID':'ubuntu','VERSION_ID':'26.04'},'amd64')
        for distro,version,arch in [('debian','26.04','amd64'),('ubuntu','24.04','amd64'),('ubuntu','26.04','arm64')]:
            with self.assertRaises(ValueError):require_supported({'ID':distro,'VERSION_ID':version},arch)

    def test_invalid_config_values(self):
        for scale,gpu,kb in [('0','auto','us'),('2; evil','auto','us'),('auto','../../bad','us'),('auto','auto','us";os.execute("x")')]:
            with self.assertRaises(ValueError):validate_options('desktop',scale,gpu,kb)
        validate_options('desktop','1.5','0000:03:00.0','us,de')

    def test_apt_removals_rejected(self):
        with self.assertRaises(ValueError):reject_apt_removals('Inst x\nRemv openssh-server [1]\n')
        reject_apt_removals('Inst waybar (1 Ubuntu)\n')

    def test_wheel_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            wheel=Path(directory)/'bad.whl'
            with zipfile.ZipFile(wheel,'w') as archive:archive.writestr('../escape','bad')
            with self.assertRaises(ValueError):extract_wheel(wheel,Path(directory)/'target')
            self.assertFalse((Path(directory)/'escape').exists())

    def test_native_audio_placeholders_survive_but_template_injection_does_not(self):
        opts=dict(profile='desktop',scale='auto',gpu='auto',keyboard='us')
        self.assertEqual(installer.render('@DEFAULT_AUDIO_SINK@',Path('/home/alice'),opts),'@DEFAULT_AUDIO_SINK@')
        with self.assertRaises(ValueError):installer.render('@HOME@',Path('/home/a"bad'),opts)


if __name__=='__main__':unittest.main()
