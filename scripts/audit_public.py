#!/usr/bin/python3
"""Audit the explicit public source tree; private caches/diagnostics are excluded."""
import ast
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'.git','.cache','__pycache__','build','dist','reports','backups','.venv'}
PATTERNS=[rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',
          rb'gh[pousr]_[A-Za-z0-9]{30,}',rb'tskey-[A-Za-z0-9_-]{20,}']

def public_files(root=ROOT):
    return sorted(p for p in root.rglob('*') if p.is_file() and not (set(p.relative_to(root).parts)&EXCLUDED))

def main():
    errors=[]
    for path in public_files():
        rel=path.relative_to(ROOT)
        if path.is_symlink(): errors.append(str(rel)+': source symlink')
        if path.suffix in ('.deb','.whl','.pem','.key') or path.name.startswith('.env'):
            errors.append(str(rel)+': private/binary artifact')
        data=path.read_bytes()
        if any(re.search(pattern,data) for pattern in PATTERNS):errors.append(str(rel)+': possible credential')
        if path.suffix=='.py' or (rel.parts[0]=='bin' and data.startswith(b'#!/usr/bin/python3')):
            try:ast.parse(data,filename=str(rel))
            except SyntaxError as e:errors.append(str(e))
        if path.suffix in ('.json','.jsonc'):
            try:json.loads(data)
            except ValueError as e:errors.append(str(rel)+': '+str(e))
        if path.suffix in ('.xml','.glade'):
            try:ET.fromstring(data)
            except ET.ParseError as e:errors.append(str(rel)+': '+str(e))
    for error in errors:print(error,file=sys.stderr)
    print(f'Public source audit: {len(public_files())} files; {len(errors)} errors')
    return bool(errors)

if __name__=='__main__':sys.exit(main())
