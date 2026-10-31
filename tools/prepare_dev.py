#!/usr/bin/python3
"""Fetch only verified palette-test wheels into .cache; no sudo or pip."""
import json
from pathlib import Path
import sys
from hflib import checked_download, extract_wheel

def main():
    if sys.version_info[:2] != (3,14):
        raise ValueError('Extended wheel lock requires Python 3.14')
    root=Path(__file__).resolve().parents[1]
    for item in json.loads((root/'locks/python-wheels.json').read_text()):
        path=checked_download(item['url'],item['sha256'],root/'.cache/wheels'/item['filename'])
        extract_wheel(path,root/'.cache/runtime/lib')
        print('Verified '+item['filename'])

if __name__=='__main__':main()
