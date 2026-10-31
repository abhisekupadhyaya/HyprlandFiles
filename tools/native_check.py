#!/usr/bin/python3
"""Validate private rendered configs with installed native parsers, never apply."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from hflib import Transaction
from installer import user_operations

def main():
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root/'.cache/runtime/lib'))
    loader=importlib.machinery.SourceFileLoader('hf_native_theme',str(root/'bin/hf-theme'))
    spec=importlib.util.spec_from_loader(loader.name,loader)
    theme=importlib.util.module_from_spec(spec);loader.exec_module(theme)
    with tempfile.TemporaryDirectory(prefix='hf-native-') as directory:
        home=Path(directory)/'home';home.mkdir()
        theme.STATE=home/'.local/state/hyprlandfiles'
        generation=theme.generate(root/'assets/royal-blue.png')
        for profile,scale in [('desktop','auto'),('laptop-server','2')]:
            opts=dict(profile=profile,scale=scale,gpu='auto',keyboard='us')
            store=Path(directory)/('backups-'+profile)
            tx=Transaction(store,home)
            backup=tx.apply(user_operations(root,home,opts,generation))
            env=dict(os.environ,HOME=str(home),XDG_CONFIG_HOME=str(home/'.config'),XDG_CACHE_HOME=str(home/'.cache'))
            command=['Hyprland','--verify-config','-c',str(home/'.config/hypr/hyprland.lua')]
            result=subprocess.run(command,text=True,capture_output=True,env=env)
            if result.returncode:
                print(result.stdout+result.stderr,file=sys.stderr)
                raise ValueError('Native Lua validation failed for '+profile)
            subprocess.run(['fuzzel','--check-config','--config',str(home/'.config/fuzzel/fuzzel.ini')],check=True,env=env)
            tx.rollback(backup)
            print('PASS native Lua and Fuzzel:',profile,'scale',scale)
    print('No installed user config, compositor, service or login was changed.')

if __name__=='__main__':main()
