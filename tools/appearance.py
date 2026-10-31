"""Dark appearance defaults, with per-file and per-key rollback; no service stop."""
import argparse
import configparser
import datetime
import json
import os
from pathlib import Path
import re
from hflib import Transaction, atomic, operation, no_symlink_parents

SCHEMA='org.gnome.desktop.interface'
DESIRED={'color-scheme':'prefer-dark','gtk-theme':'Adwaita-dark'}


def merge_settings(text, updates):
    """Preserve unrelated keys, sections and comments in existing GTK files."""
    parser=configparser.ConfigParser(interpolation=None,strict=True)
    parser.optionxform=str
    parser.read_string(text)
    result=[];inside=False;seen_section=False;pending=dict(updates)
    def flush():
        result.extend(k+'='+v+'\n' for k,v in pending.items());pending.clear()
    for line in text.splitlines(keepends=True):
        section=re.match(r'\s*\[([^]]+)\]',line)
        if section:
            if inside:flush()
            inside=section.group(1)=='Settings';seen_section|=inside
        key=re.match(r'\s*([^#;=\s][^=]*?)\s*=',line)
        if inside and key and key.group(1).strip() in updates:
            name=key.group(1).strip()
            result.append(name+'='+updates[name]+'\n');pending.pop(name,None)
        else:result.append(line if line.endswith('\n') else line+'\n')
    if not seen_section:result.append('[Settings]\n')
    flush()
    return ''.join(result)


def file_operations(root, home):
    root,home=Path(root),Path(home);ops=[]
    for folder in ('gtk-3.0','gtk-4.0'):
        source=root/'config'/folder/'settings.ini'
        defaults=configparser.ConfigParser(interpolation=None);defaults.optionxform=str
        defaults.read(source)
        target=home/'.config'/folder/'settings.ini'
        original=target.read_text() if target.is_file() else ''
        ops.append(operation(target,merge_settings(original,dict(defaults['Settings']))))
    # Seed VS Code without requiring/installing the application. Existing explicit
    # application settings (including JSONC and profiles) remain the user's choice.
    source=root/'config/Code/User/settings.json';target=home/'.config/Code/User/settings.json'
    if not target.exists() and not target.is_symlink():ops.append(operation(target,source.read_text()))
    return ops


def settings_backend():
    from gi.repository import Gio
    settings=Gio.Settings.new(SCHEMA)
    if not all(settings.is_writable(k) for k in DESIRED):raise ValueError('Appearance keys are administratively locked')
    return settings


def user_values(settings):
    return {key:(value.print_(True) if (value:=settings.get_user_value(key)) is not None else None) for key in DESIRED}


def apply_preferences(home, files_backup=None):
    from gi.repository import Gio
    home=Path(home);settings=settings_backend();before=user_values(settings)
    desired={k:"'"+v+"'" for k,v in DESIRED.items()}
    if before==desired and not files_backup:return None
    folder=home/'.local/state/hyprlandfiles/appearance/preferences'
    no_symlink_parents(folder/'probe',home)
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    snapshot=folder/stamp;snapshot.mkdir(mode=0o700)
    record=dict(schema=SCHEMA,before=before,after=desired,files_backup=str(files_backup) if files_backup else None)
    atomic(snapshot/'preferences.json',json.dumps(record,indent=2)+'\n',0o600)
    print('Appearance rollback: python3 tools/appearance.py rollback '+str(snapshot),flush=True)
    for key,value in DESIRED.items():
        if not settings.set_string(key,value):raise RuntimeError('Could not set appearance preference: '+key)
    Gio.Settings.sync()
    if user_values(settings)!=desired:raise RuntimeError('Appearance preference readback did not match')
    return snapshot


def rollback(home, snapshot):
    from gi.repository import Gio,GLib
    home,snapshot=Path(home),Path(snapshot).absolute()
    boundary=home/'.local/state/hyprlandfiles/appearance/preferences'
    no_symlink_parents(snapshot/'preferences.json',boundary)
    record=json.loads((snapshot/'preferences.json').read_text())
    if record['schema']!=SCHEMA or set(record['before'])!=set(DESIRED):raise ValueError('Unrecognized appearance snapshot')
    settings=settings_backend();current=user_values(settings)
    if any(current[k] not in (record['before'][k],record['after'][k]) for k in DESIRED):
        raise ValueError('Appearance changed since apply; merge before rollback')
    if record['files_backup']:
        Transaction(home/'.local/state/hyprlandfiles/appearance/files',home).rollback(record['files_backup'])
    for key,value in record['before'].items():
        if value is None:settings.reset(key)
        elif not settings.set_value(key,GLib.Variant.parse(None,value,None,None)):raise RuntimeError('Preference restore failed')
    Gio.Settings.sync()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('apply','rollback'))
    p.add_argument('snapshot',nargs='?',type=Path)
    a=p.parse_args();home=Path.home();root=Path(__file__).resolve().parents[1]
    if a.action=='rollback':
        if not a.snapshot:p.error('rollback needs the exact snapshot path')
        rollback(home,a.snapshot)
    else:
        if os.geteuid()==0:raise SystemExit('Run as the desktop user, without sudo')
        backup=Transaction(home/'.local/state/hyprlandfiles/appearance/files',home).apply(file_operations(root,home),adopt=True,show_rollback=False)
        apply_preferences(home,backup)
        print('Dark appearance applied. Existing application overrides are preserved.')
