import fcntl
import importlib.machinery
import importlib.util
import os
import io
import contextlib
import runpy
import signal
import socket
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'controller'))
import desktopd as desktop


class Safety(unittest.TestCase):
    def daemon(self,path):
        d=desktop.Daemon.__new__(desktop.Daemon)
        d.cfg=desktop.Config()
        d.mem=desktop.Memory()
        d.guard=os.open(path,os.O_RDWR|os.O_CREAT,0o600)
        self.addCleanup(os.close,d.guard)
        d.observe=lambda: desktop.Observation(10,'closed','active')
        return d

    def test_running_desktop_lifetime_lock_prevents_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'guard'
            d=self.daemon(path)
            with path.open('r') as holder:
                fcntl.flock(holder,fcntl.LOCK_SH)
                with patch.object(desktop,'_run') as run:
                    d.execute([desktop.Action('STOP')])
                    run.assert_not_called()

    def test_guard_is_held_until_stop_finishes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'guard'
            d=self.daemon(path)
            def stop(argv,**kwargs):
                self.assertNotIn('--no-block',argv)
                with path.open('r') as new_session:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(new_session,fcntl.LOCK_SH|fcntl.LOCK_NB)
                return type('Result',(),dict(returncode=0))()
            with patch.object(desktop,'_run',side_effect=stop):
                d.execute([desktop.Action('STOP')])
            with path.open('r') as new_session:
                fcntl.flock(new_session,fcntl.LOCK_SH|fcntl.LOCK_NB)

    def test_failed_logind_read_is_not_an_empty_session_list(self):
        r=type('Result',(),dict(returncode=1,stdout=''))()
        with patch.object(desktop,'_run',return_value=r):
            with self.assertRaises(RuntimeError):desktop.read_sessions()

    def test_closing_session_is_still_protected(self):
        s=desktop.Session('5','alice','seat0','user','wayland','greetd','closing')
        obs=desktop.Observation(10,'closed','active',(s,))
        self.assertFalse(desktop.stop_still_safe(obs,desktop.Config()))

    def test_confirmed_lock_does_not_leave_controller_busy_polling(self):
        mem=desktop.Memory(raw_lid='closed',stable_lid='closed',lock_sent={'5':1})
        obs=desktop.Observation(60,'closed','active')
        self.assertFalse(desktop.is_busy(obs,mem,desktop.Config()))


loader=importlib.machinery.SourceFileLoader('hf_lock',str(ROOT/'bin/hf-lock'))
spec=importlib.util.spec_from_loader(loader.name,loader)
locker=importlib.util.module_from_spec(spec)
loader.exec_module(locker)


class Locker(unittest.TestCase):
    def test_authentication_clears_hint_only_after_confirmation(self):
        cmd=[sys.executable,'-c','print("onLockLocked called"); print("Unlocked, exiting!")']
        with patch.object(locker,'hint') as hint,patch.object(locker,'log'):
            self.assertEqual(locker.supervise('/session',cmd),0)
            self.assertEqual([c.args[1] for c in hint.call_args_list],[True,False])

    def test_crash_after_lock_never_clears_hint(self):
        cmd=[sys.executable,'-c','print("onLockLocked called"); raise SystemExit(1)']
        with patch.object(locker,'hint') as hint,patch.object(locker,'log'),patch.object(locker.time,'sleep'):
            self.assertEqual(locker.supervise('/session',cmd),1)
            self.assertEqual([c.args[1] for c in hint.call_args_list],[True,True])


session_loader=importlib.machinery.SourceFileLoader('hf_session',str(ROOT/'bin/hf-session'))
session_spec=importlib.util.spec_from_loader(session_loader.name,session_loader)
session_module=importlib.util.module_from_spec(session_spec);session_loader.exec_module(session_module)


class SessionGuard(unittest.TestCase):
    def test_session_cleanup_finishes_before_lifetime_guard_is_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'guard';path.touch();calls=[]
            def cleanup():
                with path.open('rb') as check:
                    with self.assertRaises(BlockingIOError):fcntl.flock(check,fcntl.LOCK_EX|fcntl.LOCK_NB)
                calls.append('cleaned')
            result=session_module.run_session(path,tmp,dict(os.environ),
                [sys.executable,'-c','raise SystemExit(7)'],cleanup=cleanup)
            self.assertEqual(result,7);self.assertEqual(calls,['cleaned'])
            with path.open('rb') as check:fcntl.flock(check,fcntl.LOCK_EX|fcntl.LOCK_NB)

    def test_only_local_authenticated_greetd_sessions_can_launch(self):
        props={'Remote':'no','Seat':'seat0','User':str(os.getuid()),'Class':'user','Service':'greetd'}
        with patch.dict(os.environ,{'XDG_SESSION_ID':'test','XDG_RUNTIME_DIR':'/tmp/test-runtime'}), \
                patch.object(session_module,'property',side_effect=lambda sid,key:props[key]), \
                patch.object(session_module,'settings',return_value={'gpu':'default'}), \
                patch.object(session_module,'run_session',return_value=0) as launch:
            self.assertEqual(session_module.main(),0)
            launch.assert_called_once()
            for key,value in [('Remote','yes'),('Seat','seat1'),('User','-1'),('Class','greeter'),('Service','login'),('Service','sshd')]:
                with self.subTest(key=key,value=value),patch.dict(props,{key:value}):
                    launch.reset_mock()
                    with self.assertRaises(RuntimeError):session_module.main()
                    launch.assert_not_called()

    def test_child_does_not_inherit_lifetime_locks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'guard';path.touch()
            # An independent child should not see its parent's guard or singleton
            # fd. The parent still holds the lock until this child exits.
            script='''import os,fcntl,sys
from pathlib import Path
guard=Path(sys.argv[1]); runtime=Path(sys.argv[2])
for p in Path('/proc/self/fd').iterdir():
    try: target=p.resolve(strict=True)
    except FileNotFoundError: continue
    assert target not in (guard,runtime/'hf-session.lock'), str(target)
with guard.open('rb') as f:
    try: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: pass
    else: raise AssertionError('supervisor did not retain shared guard')
'''
            rc=session_module.run_session(path,tmp,dict(os.environ),[sys.executable,'-c',script,str(path),tmp])
            self.assertEqual(rc,0)
            with path.open('rb') as f:
                fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)


menu_loader=importlib.machinery.SourceFileLoader('hf_menu',str(ROOT/'bin/hf-menu'))
menu_spec=importlib.util.spec_from_loader(menu_loader.name,menu_loader)
menu_module=importlib.util.module_from_spec(menu_spec);menu_loader.exec_module(menu_module)


class SessionMenu(unittest.TestCase):
    def test_terminal_launched_from_bar_has_an_independent_scope(self):
        with patch.object(sys,'argv',['hf-menu','main']), \
                patch.object(menu_module,'choose',return_value='Terminal'), \
                patch.object(menu_module.subprocess,'Popen') as launch:
            menu_module.main()
        self.assertEqual(launch.call_args.args[0],
            ['systemd-run','--user','--scope','--collect','--quiet','--','ghostty'])

    def test_confirmed_logout_survives_stopping_the_bar(self):
        choice='Log out — return to login'
        with patch.object(sys,'argv',['hf-menu','power']), \
                patch.object(menu_module,'choose',side_effect=[choice,'Confirm: '+choice]), \
                patch.object(menu_module.subprocess,'run') as run:
            menu_module.main()
        self.assertEqual(run.call_args.args[0],
            ['systemd-run','--user','--scope','--collect','--quiet','--','hyprshutdown','--no-fork'])

    def test_server_mode_uses_installed_command_after_confirmation(self):
        choice='Server mode — log out and hide login'
        with patch.object(sys,'argv',['hf-menu','power']), \
                patch.object(menu_module,'choose',side_effect=[choice,'Confirm: '+choice]), \
                patch.object(menu_module.subprocess,'run') as run:
            menu_module.main()
        executable=Path(run.call_args.args[0][0])
        self.assertEqual(executable,ROOT/'bin/hf-desktop')
        self.assertTrue(executable.is_file())
        self.assertEqual(run.call_args.args[0][1:],['off'])

    def test_cancelled_server_mode_does_not_change_session(self):
        with patch.object(sys,'argv',['hf-menu','power']), \
                patch.object(menu_module,'choose',side_effect=['Server mode','Cancel']), \
                patch.object(menu_module.subprocess,'run') as run:
            menu_module.main()
            run.assert_not_called()


desktop_loader=importlib.machinery.SourceFileLoader('hf_desktop',str(ROOT/'bin/hf-desktop'))
desktop_spec=importlib.util.spec_from_loader(desktop_loader.name,desktop_loader)
desktop_module=importlib.util.module_from_spec(desktop_spec);desktop_loader.exec_module(desktop_module)


class ServerLogout(unittest.TestCase):
    def test_logout_has_its_own_scope_even_when_invoked_directly(self):
        from types import SimpleNamespace
        with patch.dict(os.environ,{'HYPRLAND_INSTANCE_SIGNATURE':'test-instance'}), \
                patch.object(desktop_module,'ask',return_value={'desktop_sessions':[{'id':'test'}]}) as ask, \
                patch.object(desktop_module.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run:
            desktop_module.off()
        self.assertEqual([call.args[0] for call in ask.call_args_list],['status','off'])
        self.assertEqual(run.call_args.args[0],
            ['systemd-run','--user','--scope','--collect','--quiet','--','hyprshutdown','--no-fork'])

    def test_failed_logout_restores_login_screen_policy(self):
        from types import SimpleNamespace
        with patch.dict(os.environ,{'HYPRLAND_INSTANCE_SIGNATURE':'test-instance'}), \
                patch.object(desktop_module,'ask',return_value={'desktop_sessions':[{'id':'test'}]}) as ask, \
                patch.object(desktop_module.subprocess,'run',return_value=SimpleNamespace(returncode=1)):
            with self.assertRaises(RuntimeError):desktop_module.off()
        self.assertEqual([call.args[0] for call in ask.call_args_list],['status','off','on'])


start_loader=importlib.machinery.SourceFileLoader('hf_session_start',str(ROOT/'bin/hf-session-start'))
start_spec=importlib.util.spec_from_loader(start_loader.name,start_loader)
start_module=importlib.util.module_from_spec(start_spec);start_loader.exec_module(start_module)


class GraphicalStartup(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.runtime=Path(tmp.name)
        sock=socket.socket(socket.AF_UNIX);self.addCleanup(sock.close)
        sock.bind(str(self.runtime/'wayland-test'))
        self.env=dict(XDG_SESSION_ID='test-session',XDG_RUNTIME_DIR=str(self.runtime),
            WAYLAND_DISPLAY='wayland-test',HYPRLAND_INSTANCE_SIGNATURE='test-instance',
            DBUS_SESSION_BUS_ADDRESS='unix:path=/wrong-greeter-bus')
        self.props='User='+str(os.getuid())+'\nSeat=seat0\nRemote=no\nClass=user\nService=greetd\nState=active\n'

    def test_compositor_environment_is_imported_before_session_target_starts(self):
        with patch.object(start_module.subprocess,'check_output',return_value=self.props), \
                patch.object(start_module.subprocess,'run') as run:
            self.assertEqual(start_module.start(self.env),0)
        first,second=run.call_args_list
        self.assertEqual(first.args[0][:2],['dbus-update-activation-environment','--systemd'])
        self.assertIn('WAYLAND_DISPLAY',first.args[0])
        self.assertIn('HYPRLAND_INSTANCE_SIGNATURE',first.args[0])
        self.assertEqual(first.kwargs['env']['DBUS_SESSION_BUS_ADDRESS'],'unix:path='+str(self.runtime/'bus'))
        self.assertEqual(second.args[0],['systemctl','--user','start','hf-session.target',
            'waybar.service','hyprpaper.service','swaync.service','hypridle.service'])

    def test_ssh_login_cannot_activate_graphical_helpers(self):
        with patch.object(start_module.subprocess,'check_output',return_value=self.props.replace('Remote=no','Remote=yes')), \
                patch.object(start_module.subprocess,'run') as run:
            with self.assertRaises(RuntimeError):start_module.start(self.env)
            run.assert_not_called()

    def test_missing_compositor_refuses_activation(self):
        self.env['WAYLAND_DISPLAY']='missing-socket'
        with patch.object(start_module.subprocess,'check_output',return_value=self.props), \
                patch.object(start_module.subprocess,'run') as run:
            with self.assertRaises(RuntimeError):start_module.start(self.env)
            run.assert_not_called()

    def test_closing_session_cannot_restart_graphical_helpers(self):
        with patch.object(start_module.subprocess,'check_output',return_value=self.props.replace('State=active','State=closing')), \
                patch.object(start_module.subprocess,'run') as run:
            with self.assertRaises(RuntimeError):start_module.start(self.env)
            run.assert_not_called()

    def test_shutdown_stops_session_targets_and_clears_compositor_environment(self):
        from types import SimpleNamespace
        with patch.object(sys,'argv',['hf-session-stop']), \
                patch.object(signal,'signal'), \
                patch('subprocess.run',return_value=SimpleNamespace(returncode=0,stderr='')) as run, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as stopped:runpy.run_path(str(ROOT/'bin/hf-session-stop'),run_name='__main__')
        self.assertEqual(stopped.exception.code,0);self.assertEqual(output.getvalue(),'OK\n')
        self.assertIn('hf-session.target',run.call_args_list[0].args[0])
        self.assertIn('graphical-session.target',run.call_args_list[0].args[0])
        self.assertEqual(run.call_args_list[1].args[0][:3],['systemctl','--user','unset-environment'])
        self.assertIn('WAYLAND_DISPLAY=',run.call_args_list[2].args[0])


if __name__=='__main__':unittest.main()
