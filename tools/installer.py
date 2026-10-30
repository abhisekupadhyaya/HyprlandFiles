#!/usr/bin/python3
"""HyprlandFiles installer. ./install.sh plan is read-only; setup asks first."""
from __future__ import annotations

import argparse
import fcntl
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import pwd
import shlex
import shutil
import subprocess
import sys

from hflib import (PREFIX, ROOT_STATE, VERSION, Transaction, atomic, checked_download,
                   extract_wheel, fingerprint, managed_state, operation, os_release,
                   output, reject_apt_removals, require_supported, run, validate_options, no_symlink_parents)

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT/'locks/ubuntu-26.04-amd64.json').read_text())
AUDIO = ('pipewire.service','pipewire.socket','pipewire-pulse.service',
         'pipewire-pulse.socket','wireplumber.service')
DESKTOP = ('waybar.service','hypridle.service','hyprpaper.service','swaync.service')
BASE_PACKAGES = ('python3','python3-gi','gir1.2-gtk-3.0','dbus-user-session','libpam-systemd',
                 'pipewire','pipewire-pulse','wireplumber','xdg-desktop-portal',
                 'xdg-desktop-portal-gtk','xwayland','thunar','pavucontrol','playerctl',
                 'brightnessctl','wl-clipboard','grim','slurp','libnotify-bin',
                 'fonts-inter','fonts-jetbrains-mono','fonts-noto-color-emoji',
                 'adwaita-icon-theme','upower','less','util-linux','ca-certificates')


def supported():
    require_supported(os_release(), output(['dpkg','--print-architecture']))
    if sys.version_info[:2] != (3,14):
        raise ValueError('This lock requires Ubuntu Python 3.14. Do not replace system Python.')


def gui_sessions():
    ids=output(['loginctl','list-sessions','--no-legend','--no-pager'])
    sessions=[]
    for line in ids.splitlines():
        sid=line.split()[0]
        props=dict(x.split('=',1) for x in output(['loginctl','show-session',sid,'-p','Class','-p','Seat','-p','Type','-p','Remote']).splitlines())
        if props.get('Class')=='user' and props.get('Remote')=='no' and props.get('Seat')=='seat0' and props.get('Type') in ('wayland','x11','mir'):
            sessions.append(sid)
    return sessions


def no_gui():
    if gui_sessions():
        raise ValueError('A graphical session is running. Save work and log out yourself; installer never closes it.')


def package_pins(packages, restrict_ppa=True):
    text='# HyprlandFiles: deliberate desktop updates. Ubuntu security updates remain enabled.\n'
    if restrict_ppa:
        text+='\nPackage: *\nPin: release o=LP-PPA-cppiber-hyprland\nPin-Priority: 1\n'
    for name,version in sorted(packages.items()):
        text+=f'\nPackage: {name}\nPin: version {version}\nPin-Priority: 1001\n'
    return text


def options(a):
    return dict(profile=a.profile,scale=a.scale,gpu=a.gpu,keyboard=a.keyboard)


def render(text, home, opts):
    # JSON/Lua string encoding prevents a home path from becoming executable Lua.
    # CSS/INI consumers need escaping too; require conventional Ubuntu home paths.
    if not __import__('re').fullmatch(r'/[A-Za-z0-9_./-]+',str(home)):
        raise ValueError('Home path contains unsupported config characters; use a conventional Ubuntu home directory')
    replacements={'@HOME@':str(home),'@KEYBOARD@':opts['keyboard'],
                  '@SCALE_LUA@':json.dumps('auto') if opts['scale']=='auto' else opts['scale'],
                  '@LID_ENABLED@':'true' if opts['profile']=='laptop-server' else 'false'}
    for k,v in replacements.items(): text=text.replace(k,v)
    if __import__('re').search(r'@[A-Z_]+@',text.replace('@DEFAULT_AUDIO_SINK@','').replace('@DEFAULT_AUDIO_SOURCE@','')): raise ValueError('Unresolved configuration placeholder')
    return text


def user_operations(root, home, opts, generation=None):
    operations=[]
    for folder in ('hypr','waybar','kitty','fuzzel','swaync','xdg-desktop-portal'):
        for source in sorted((root/'config'/folder).rglob('*')):
            if source.is_file():
                relative=source.relative_to(root/'config')
                operations.append(operation(home/'.config'/relative,render(source.read_text(),home,opts)))
    # Waybar hides absent batteries/backlights; no hardcoded device names.
    for unit in DESKTOP:
        operations.append(operation(home/'.config/systemd/user/graphical-session.target.wants'/unit,link='/usr/lib/systemd/user/'+unit))
    operations.append(operation(home/'.config/systemd/user/hyprpolkitagent.service',link='/dev/null'))
    for unit in ('thunar.service','xdg-desktop-portal-gtk.service','xdg-desktop-portal-hyprland.service'):
        operations.append(operation(home/'.config/systemd/user'/f'{unit}.d/hyprlandfiles.conf','[Unit]\nPartOf=graphical-session.target\nAfter=graphical-session.target\n'))
    for source in sorted((root/'applications').glob('*.desktop')):
        operations.append(operation(home/'.local/share/applications'/source.name,source.read_text()))
    operations.append(operation(home/'.config/hyprlandfiles/settings.json',json.dumps(opts,indent=2)+'\n'))
    state=home/'.local/state/hyprlandfiles'
    operations.append(operation(home/'.config/hypr/hyprpaper.conf',link=str(state/'current/hyprpaper.conf')))
    if generation:
        operations.append(operation(state/'current',link=str(generation)))
    # Default/socket activation in the user's own tree overrides global changes.
    for unit in AUDIO:
        for target in ('default.target','sockets.target'):
            p=home/'.config/systemd/user'/f'{target}.wants'/unit
            if os.path.lexists(p): operations.append(operation(p,remove=True))
    return operations


def system_operations(root, account, opts):
    operations=[]
    # Explicit public payload allowlist. No Git metadata, inventory, host backups,
    # local cache, personal home files or downloaded artifacts are copied.
    for folder in ('bin','python','controller','config','applications','assets','docs','locks','patches','tools','LICENSES'):
        for source in sorted((root/folder).rglob('*')):
            if source.is_symlink(): raise ValueError('Payload symlink refused: '+str(source))
            if source.is_file() and '__pycache__' not in source.parts and source.suffix!='.pyc':
                rel=source.relative_to(root)
                executable=folder=='bin' or rel.as_posix()=='controller/desktopd.py'
                operations.append(operation(PREFIX/rel,source.read_bytes(),0o755 if executable else 0o644))
    operations.append(operation(PREFIX/'LICENSE',(root/'LICENSE').read_bytes()))
    for source in sorted((root/'bin').iterdir()):
        if source.is_file(): operations.append(operation(Path('/usr/local/bin')/source.name,link=str(PREFIX/'bin'/source.name)))
    for source in ('hf-desktopd.service',):
        operations.append(operation(Path('/etc/systemd/system')/source,(root/'system'/source).read_text()))
    operations.append(operation('/etc/systemd/system/greetd.service.d/hyprlandfiles.conf',(root/'system/greetd-override.conf').read_text()))
    greeter=pwd.getpwnam('_greetd')
    config='[terminal]\nvt = 7\nswitch = true\n\n[default_session]\ncommand = "/usr/local/bin/hf-greeter-session"\nuser = "'+greeter.pw_name+'"\n'
    operations.append(operation('/etc/greetd/config.toml',config))
    for original,target in (('hyprlandfiles.glade','hyprlandfiles.glade'),('settings.json','nwg-hello.json'),('style.css','nwg-hello.css'),('vocabulary.json','en_US')):
        operations.append(operation(Path('/etc/nwg-hello')/target,(root/'config/login-select'/original).read_text()))
    operations.append(operation('/etc/greetd/hyprlandfiles-wallpaper.png',(root/'assets/royal-blue.png').read_bytes()))
    operations.append(operation('/etc/greetd/hyprlandfiles-labwc/rc.xml',(root/'config/login-select/labwc-rc.xml').read_text()))
    for name in ('autostart','shutdown','environment'):
        operations.append(operation('/etc/greetd/hyprlandfiles-labwc/'+name,''))
    operations.append(operation('/etc/hyprlandfiles/session.json',json.dumps(dict(opts,users=[account.pw_name]),indent=2)+'\n'))
    conf=f'profile = {opts["profile"]}\nallowed_users = {account.pw_name}\ndocked_policy = strict\npanel_control = '+('yes' if opts['profile']=='laptop-server' else 'no')+'\n'
    operations.append(operation('/etc/hyprlandfiles/hyprlandfiles.conf',conf))
    if opts['profile']=='laptop-server':
        operations.append(operation('/etc/systemd/logind.conf.d/90-hyprlandfiles-lid.conf','[Login]\nHandleLidSwitch=ignore\nHandleLidSwitchExternalPower=ignore\nHandleLidSwitchDocked=ignore\n'))
    for unit in AUDIO:
        for target in ('default.target','sockets.target'):
            p=Path('/etc/systemd/user')/f'{target}.wants'/unit
            if os.path.lexists(p):
                if not p.is_symlink(): raise ValueError('Unexpected audio enabling file: '+str(p))
                operations.append(operation(p,remove=True))
        operations.append(operation(Path('/etc/systemd/user')/f'{unit}.d/hyprlandfiles.conf','[Unit]\nPartOf=graphical-session.target\nAfter=graphical-session.target\n'))
    for unit in ('pipewire.service','pipewire.socket','pipewire-pulse.service','pipewire-pulse.socket'):
        operations.append(operation(Path('/etc/systemd/user/graphical-session.target.wants')/unit,link='/usr/lib/systemd/user/'+unit))
    # Capture startup links explicitly; do not run broad systemctl disable.
    for name in ('display-manager.service','graphical.target.wants/greetd.service'):
        p=Path('/etc/systemd/system')/name
        if os.path.lexists(p):
            if not p.is_symlink() or Path(os.readlink(p)).name!='greetd.service':
                raise ValueError('Another display manager is configured: '+str(p))
            operations.append(operation(p,remove=True))
    return operations


def plan(a):
    supported()
    opts=options(a)
    print(f'HyprlandFiles {VERSION} — reviewed install plan')
    print('Profile:',a.profile,'| keyboard:',a.keyboard,'| display scale:',a.scale,'| GPU:',a.gpu)
    print('Target account:',pwd.getpwuid(os.getuid()).pw_name)
    print('Ubuntu 26.04 amd64; exact Hyprland 0.57.0 stack from the cppiber PPA.')
    print('Source trust: https://launchpad.net/~cppiber/+archive/ubuntu/hyprland')
    print('Signing key: A54D23B62FF3FCC76EFF71E8FDBAAA1CF0CCF48E')
    print('PPA, exact ABI pins, root-owned runtime, greetd + patched nwg-hello/labwc, desktop-only audio.')
    print('Packages:', ' '.join([*(f'{k}={v}' for k,v in LOCK['packages'].items()),*BASE_PACKAGES,'nwg-hello='+LOCK['nwg_hello']['version']]))
    print('System config: /etc/{greetd,nwg-hello,hyprlandfiles,systemd}; runtime:',PREFIX)
    print('User config: per-file ~/.config/{hypr,waybar,kitty,fuzzel,swaync,xdg-desktop-portal,systemd}; desktop entries.')
    if a.profile=='laptop-server': print('Lid policy: ignore lid suspend on AC/battery/docked; lock the existing session on close. Takes effect after reboot.')
    print('Activation: enable controller for next boot only. No automatic logout, reboot or logind restart.')
    print('Preserved: disks, network/Netplan, SSH/Tailscale, firewall, drivers, bootloader, PAM policy, OS security updates.')
    print('Existing files: refused unless identical/managed, or explicitly adopted with permission-preserving backups.')
    print('Rollback: per-file snapshots in /var/lib/hyprlandfiles/backups and ~/.local/state/hyprlandfiles/backups; packages retained.')
    conflicts=[]
    home=Path.home()
    for op in user_operations(ROOT,home,opts):
        if os.path.lexists(op['path']): conflicts.append(op['path'])
    if conflicts: print('Existing user paths requiring review (no content read):\n'+'\n'.join(conflicts))


def system_install(a):
    if os.geteuid()!=0: raise ValueError('System phase requires sudo')
    os.umask(0o022)
    supported(); no_gui()
    if output(['systemctl','get-default'])!='multi-user.target':
        raise ValueError('Expected Ubuntu Server multi-user.target. Changing an existing desktop boot target requires manual review.')
    account=pwd.getpwnam(a.user)
    if account.pw_uid<1000 or account.pw_shell in ('/bin/false','/usr/sbin/nologin'):
        raise ValueError('Choose an existing regular local login account')
    if Path(account.pw_dir).is_symlink(): raise ValueError('Symlink home requires manual review')
    if a.profile=='laptop-server' and not list(Path('/proc/acpi/button/lid').glob('*/state')):
        raise ValueError('No readable ACPI lid state. Use desktop profile or review hardware support first.')
    for name in ('greetd.service','display-manager.service','hf-desktopd.service'):
        if subprocess.run(['systemctl','is-active','--quiet',name]).returncode==0:
            raise ValueError('An existing display manager is active. Installer will not stop it.')
    if Path('/etc/greetd/config.toml').exists() and not (ROOT_STATE/'installed.json').exists() and not a.adopt:
        raise ValueError('Existing greetd configuration; review and explicitly --adopt before replacing it')
    no_symlink_parents(ROOT_STATE/'installed.json',Path('/'))
    if (ROOT_STATE/'installed.json').is_file():
        previous=json.loads((ROOT_STATE/'installed.json').read_text())
        if previous['options']['profile']!=a.profile:
            raise ValueError('Profile migration requires a reviewed lid-policy change; retain the installed profile on rerun')
    ROOT_STATE.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.chmod(ROOT_STATE,0o700)
    with (ROOT_STATE/'installer.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        store=ROOT_STATE/'backups'
        tx=Transaction(store,Path('/'),managed_state(store))
        source_ops=[operation('/etc/apt/sources.list.d/hyprlandfiles.sources',(ROOT/'system/hyprlandfiles.sources').read_text()),
                    operation('/etc/apt/preferences.d/60-hyprlandfiles-abi.pref',package_pins(dict({k:LOCK['packages'][k] for k in LOCK['ppa_packages']}, **{'nwg-hello':LOCK['nwg_hello']['version']}))),
                    operation('/etc/systemd/system/greetd.service',link='/dev/null')]
        before_mask=fingerprint('/etc/systemd/system/greetd.service')
        if before_mask != 'absent':
            raise ValueError('Existing greetd unit override requires manual review')
        package_targets=[Path('/etc/greetd/config.toml'),*[Path('/etc/nwg-hello')/x for x in ('nwg-hello.json','nwg-hello.css','en_US')]]
        package_targets += [Path('/etc/systemd/user')/f'{target}.wants'/unit for unit in AUDIO for target in ('default.target','sockets.target')]
        package_targets += [Path('/etc/systemd/system')/name for name in ('display-manager.service','graphical.target.wants/greetd.service')]
        pre_package={str(p):fingerprint(p) for p in package_targets}
        tx.apply(source_ops,adopt=a.adopt)
        run(['systemctl','daemon-reload'])
        run(['apt-get','update'])
        from build_greeter import build
        audited=build(ROOT,ROOT_STATE/'cache/greeter')
        exact=[f'{k}={v}' for k,v in LOCK['packages'].items()]
        command=['apt-get','--no-remove','--no-install-recommends','-o','Dpkg::Options::=--force-confold','install',*exact,*BASE_PACKAGES,str(audited)]
        simulation=output([command[0],'--simulate',*command[1:]])
        reject_apt_removals(simulation)
        print(simulation,flush=True)
        # Only explicit allowlisted desktop changes and new dependencies are
        # accepted. Existing shared-package upgrades require normal OS upkeep.
        existing=dict(
            line.split('\t',1) for line in output(['dpkg-query','-W','-f=${binary:Package}\t${Version}\n']).splitlines() if '\t' in line)
        allowed=set(LOCK['packages'])|{'nwg-hello'}
        for line in simulation.splitlines():
            parts=line.split()
            if parts and parts[0]=='Inst' and parts[1] in existing and parts[1].split(':')[0] not in allowed:
                raise ValueError('APT would change an existing unrelated package: '+parts[1]+'. Update Ubuntu separately, then retry.')
        run([command[0],'--yes',*command[1:]],env=dict(os.environ,DEBIAN_FRONTEND='noninteractive',NEEDRESTART_MODE='l'))
        # Verify and prepare the colour runtime BEFORE enabling any boot path.
        runtime=ROOT_STATE/'cache/runtime/lib'
        runtime.mkdir(parents=True,exist_ok=True)
        for item in json.loads((ROOT/'locks/python-wheels.json').read_text()):
            wheel=checked_download(item['url'],item['sha256'],ROOT_STATE/'cache'/item['filename'])
            extract_wheel(wheel,runtime)
        # Only newly package-created defaults can be adopted without --adopt.
        known=managed_state(store)
        for path,before in pre_package.items():
            if before=='absent': known[path]=fingerprint(path)
        tx=Transaction(store,Path('/'),known)
        ops=system_operations(ROOT,account,options(a))
        # Every installed runtime file participates in the same backup journal.
        runtime_ops=[operation(PREFIX/'runtime/lib'/p.relative_to(runtime),p.read_bytes()) for p in sorted(runtime.rglob('*')) if p.is_file()]
        ops=runtime_ops+ops
        if before_mask=='absent': ops.append(operation('/etc/systemd/system/greetd.service',remove=True))
        else: raise ValueError('greetd was masked before install; unmask only after administrator review')
        tx.apply(ops,adopt=a.adopt)
        # Cache starts empty; the native chooser remembers users after login.
        # Existing caches are kept, never read/printed/copied to the repository.
        run(['systemctl','daemon-reload'])
        run(['systemd-analyze','verify','/etc/systemd/system/hf-desktopd.service','greetd.service'])
        atomic(ROOT_STATE/'installed.json',json.dumps(dict(version=VERSION,user=account.pw_name,options=options(a),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip()),indent=2)+'\n',0o600)
        print('System stage installed; not enabled yet. Complete user phase before next-boot enablement.')


def theme_module(root):
    loader=importlib.machinery.SourceFileLoader('hf_theme_install',str(root/'bin/hf-theme'))
    spec=importlib.util.spec_from_loader(loader.name,loader)
    module=importlib.util.module_from_spec(spec);loader.exec_module(module)
    return module


def user_install(a):
    if os.geteuid()==0: raise ValueError('Run the user phase as the desktop account, not root')
    no_gui()
    if not (PREFIX/'runtime/lib').is_dir(): raise ValueError('Run the system stage first')
    actual=json.loads(Path('/etc/hyprlandfiles/session.json').read_text())
    if actual['profile']!=a.profile: raise ValueError('User profile must match the installed system profile: '+actual['profile'])
    home=Path.home();store=home/'.local/state/hyprlandfiles/backups'
    no_symlink_parents(store/'manifest-probe',home)
    store.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (store.parent/'installer.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        tx=Transaction(store,home,managed_state(store))
        theme=theme_module(PREFIX)
        # Prepare (never apply) a complete generation. Existing selected palette
        # is preserved on rerun. State/current itself is journalled separately.
        if (theme.STATE/'current/complete').is_file(): generation=(theme.STATE/'current').resolve()
        else: generation=theme.generate(Path(a.wallpaper).resolve() if a.wallpaper else PREFIX/'assets/royal-blue.png')
        ops=user_operations(PREFIX,home,options(a),generation)
        tx.apply(ops,adopt=a.adopt)
        run(['systemctl','--user','daemon-reload'])
        verify=run(['Hyprland','--verify-config','-c',home/'.config/hypr/hyprland.lua'],text=True,capture_output=True)
        print(verify.stdout)
        print('User files installed and native Lua parser passed. Start local login after a saved-work reboot; SSH never starts a desktop.')


def enable():
    if os.geteuid()!=0: return run(['sudo','python3',ROOT/'tools/installer.py','enable']).returncode
    no_gui()
    installed=json.loads((ROOT_STATE/'installed.json').read_text())
    account=pwd.getpwnam(installed['user'])
    home=Path(account.pw_dir)
    if not (home/'.config/hypr/hyprland.lua').is_file() or not (home/'.local/state/hyprlandfiles/current/complete').is_file():
        raise ValueError('Complete the user stage before enabling graphical login')
    tx=Transaction(ROOT_STATE/'backups',Path('/'),managed_state(ROOT_STATE/'backups'))
    tx.apply([operation('/etc/systemd/system/multi-user.target.wants/hf-desktopd.service',link='/etc/systemd/system/hf-desktopd.service')])
    run(['systemctl','daemon-reload'])
    print('Controller enabled for next boot only. No service started; choose your own saved-work reboot window.')


def doctor():
    failures=[]
    def check(label,argv):
        p=subprocess.run(argv,text=True,capture_output=True)
        good=p.returncode==0
        print(('PASS ' if good else 'FAIL ')+label)
        if not good: failures.append(label)
        return p
    supported()
    for name,version in LOCK['packages'].items():
        p=check('installed '+name,['dpkg-query','-W','-f=${Version}',name])
        if p.returncode==0 and p.stdout.strip()!=version:
            print('FAIL version differs from lock: '+name);failures.append(name)
    p=check('privacy-patched greeter',['dpkg-query','-W','-f=${Version}','nwg-hello'])
    if p.stdout.strip()!=LOCK['nwg_hello']['version']:failures.append('greeter version')
    for user in (False,True):
        args=['systemctl',*(['--user'] if user else []),'--failed','--no-legend','--plain','--no-pager']
        p=check(('user' if user else 'system')+' failure query',args)
        if p.stdout.strip(): print('FAIL failed units exist; inspect with systemctl --failed');failures.append('failed units')
    p=check('Lua parser',['Hyprland','--verify-config','-c',str(Path.home()/'.config/hypr/hyprland.lua')])
    if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        p=check('live compositor',['hyprctl','configerrors'])
        if p.stdout.strip(): failures.append('live config errors')
        p=check('native output',['hyprctl','monitors','-j'])
        if p.returncode==0:
            for m in json.loads(p.stdout): print(f"  {m['name']}: {m['width']}x{m['height']} scale {m['scale']}")
    print('Physical acceptance is separate: docs/acceptance.md. No password, network key or token was read.')
    return bool(failures)


def rollback(a):
    snapshot=Path(a.snapshot).absolute()
    root_snapshot=snapshot.is_relative_to(ROOT_STATE/'backups')
    if root_snapshot and os.geteuid()!=0:
        return run(['sudo','python3',ROOT/'tools/installer.py','rollback',snapshot]).returncode
    no_gui()
    if root_snapshot:
        # This is an explicit rollback action. Refuse a live greeter as well;
        # the documented controller-off command is a separate operator step.
        if subprocess.run(['systemctl','is-active','--quiet','greetd.service']).returncode==0:
            raise ValueError('Hide the idle login first with hf-desktop off; never stop an authenticated desktop')
        if subprocess.run(['systemctl','is-active','--quiet','hf-desktopd.service']).returncode==0:
            raise ValueError('Stop hf-desktopd from TTY/SSH before root rollback; see docs/rollback.md')
        Transaction(ROOT_STATE/'backups',Path('/')).rollback(snapshot)
        run(['systemctl','daemon-reload'])
    else:
        if os.geteuid()==0: raise ValueError('User rollback must run as that user')
        Transaction(Path.home()/'.local/state/hyprlandfiles/backups',Path.home()).rollback(snapshot)
        run(['systemctl','--user','daemon-reload'])
    print('Files restored. Packages and cache retained; OS security updates unchanged.')


def freeze(a):
    if os.geteuid()!=0: raise ValueError('Freeze requires sudo; first finish docs/acceptance.md')
    packages=dict(LOCK['packages'],**{'nwg-hello':LOCK['nwg_hello']['version']})
    for name,version in packages.items():
        if output(['dpkg-query','-W','-f=${Version}',name])!=version:
            raise ValueError('Version differs from tested lock: '+name)
    tx=Transaction(ROOT_STATE/'backups',Path('/'),managed_state(ROOT_STATE/'backups'))
    tx.apply([operation('/etc/apt/preferences.d/70-hyprlandfiles-tools.pref',package_pins(packages,False))])
    print('Desktop pins applied. Review monthly and promptly for security advisories; see docs/updates.md.')


def setup(a):
    if os.geteuid()==0: raise ValueError('Run ./install.sh as your regular sudo-capable account; it asks for sudo when needed')
    plan(a)
    no_gui()
    store=Path.home()/'.local/state/hyprlandfiles/backups'
    Transaction(store,Path.home(),managed_state(store)).apply(user_operations(ROOT,Path.home(),options(a)),adopt=a.adopt,dry_run=True)
    if not a.yes:
        if not sys.stdin.isatty(): raise ValueError('Interactive terminal required, or review plan and explicitly use --yes')
        if input('Install this plan (PPA trust, packages, login files and next-boot controller)? Type INSTALL: ')!='INSTALL':
            print('Cancelled. No changes.');return
        if a.adopt and input('Existing files will be backed up and replaced. Type ADOPT: ')!='ADOPT':
            print('Cancelled. No changes.');return
    command=['sudo','python3',ROOT/'tools/installer.py','system','--user',pwd.getpwuid(os.getuid()).pw_name,
             '--profile',a.profile,'--scale',a.scale,'--gpu',a.gpu,'--keyboard',a.keyboard]
    if a.adopt: command.append('--adopt')
    run(command)
    user_install(a)
    run(['sudo','python3',ROOT/'tools/installer.py','enable'])
    print('Setup complete; hardware acceptance remains. Read docs/acceptance.md before freezing or calling this machine validated.')
    print('Save work, keep a recovery TTY/SSH route, then reboot manually when ready. No reboot was issued.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',nargs='?',default='setup',choices=('setup','plan','doctor','user','system','enable','rollback','freeze','version'))
    parser.add_argument('snapshot',nargs='?')
    parser.add_argument('--profile',choices=('desktop','laptop-server'),default='desktop')
    parser.add_argument('--scale',default='auto')
    parser.add_argument('--gpu',default='auto')
    parser.add_argument('--keyboard',default='us')
    parser.add_argument('--wallpaper',help='Local still image for initial palette; existing selections are preserved')
    parser.add_argument('--adopt',action='store_true',help='Explicitly back up and replace conflicting individual files')
    parser.add_argument('--yes',action='store_true',help='Approve the displayed setup plan without interactive confirmation')
    parser.add_argument('--user',help=argparse.SUPPRESS)
    a=parser.parse_args()
    validate_options(a.profile,a.scale,a.gpu,a.keyboard)
    if a.action=='version': print(VERSION);return 0
    if a.action=='rollback' and not a.snapshot:parser.error('rollback needs an exact BACKUP path')
    if a.action=='system' and not a.user:parser.error('internal system phase requires --user')
    return {'setup':lambda:setup(a),'plan':lambda:plan(a),'system':lambda:system_install(a),
            'user':lambda:user_install(a),'doctor':doctor,'enable':enable,'rollback':lambda:rollback(a),'freeze':lambda:freeze(a)}[a.action]()


if __name__=='__main__':
    try: sys.exit(main())
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        sys.exit('HyprlandFiles: '+str(error)+'\nNo automatic logout/reboot/removal or error-state clearing was performed. Preserve any printed BACKUP paths.')
