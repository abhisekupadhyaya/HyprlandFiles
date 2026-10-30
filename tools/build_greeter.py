"""Reproducible patched nwg-hello .deb from a checksum-locked Ubuntu package."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from hflib import checked_download, run

EPOCH = 1793383200


def build(root, cache, base=None):
    root, cache = Path(root), Path(cache)
    record = json.loads((root/'locks/ubuntu-26.04-amd64.json').read_text())['nwg_hello']
    cache.mkdir(parents=True, exist_ok=True)
    source = Path(base) if base else checked_download(record['url'], record['sha256'], cache/'nwg-hello-original.deb')
    if hashlib.sha256(source.read_bytes()).hexdigest() != record['sha256']:
        raise ValueError('Original nwg-hello checksum mismatch')
    with tempfile.TemporaryDirectory(prefix='build-nwg-', dir=cache) as directory:
        tree = Path(directory)/'root'
        run(['dpkg-deb','--extract',source,tree])
        run(['dpkg-deb','--control',source,tree/'DEBIAN'])
        rel = 'usr/lib/python3/dist-packages/nwg_hello/'
        tools = tree/rel/'tools.py'
        original = tools.read_text()
        marker = 'def greetd(client, json_req, log=False):'
        if original.count(marker) != 1:
            raise ValueError('Unexpected upstream IPC source')
        modified = original[:original.index(marker)] + (root/'patches/nwg-greetd-ipc.py').read_text()
        tools.write_text(modified)
        patch = ''.join(difflib.unified_diff(original.splitlines(True),modified.splitlines(True),fromfile='a/'+rel+'tools.py',tofile='b/'+rel+'tools.py'))
        ui = tree/rel/'ui.py'
        original = ui.read_text()
        modified = original
        lines = ['            eprint(f"user: {user}", log=self.log)\n',
                 '            eprint(f"password: {\'*\' * len(password)}", log=self.log)\n',
                 '            eprint(f"cmd: {cmd}", log=self.log)\n',
                 '            eprint(f"env vars: {self.settings[\'env-vars\']}", log=self.log)\n']
        for line in lines:
            if modified.count(line) != 1:
                raise ValueError('Unexpected UI source; review privacy patch')
            modified = modified.replace(line,'')
        ui.write_text(modified)
        patch += ''.join(difflib.unified_diff(original.splitlines(True),modified.splitlines(True),fromfile='a/'+rel+'ui.py',tofile='b/'+rel+'ui.py'))
        if (root/'patches/nwg-hello-0.4.2-privacy-and-ipc.patch').read_text() != patch:
            raise ValueError('Generated diff differs from the reviewed patch')
        control=tree/'DEBIAN/control'
        text=control.read_text().replace('Version: 0.4.2-1\n','Version: '+record['version']+'\n')
        text=text.replace('Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>\n','Maintainer: HyprlandFiles contributors <noreply@localhost>\n')
        control.write_text(text)
        sums=[]
        for path in sorted(tree.rglob('*')):
            if path.is_file() and not path.is_symlink() and 'DEBIAN' not in path.relative_to(tree).parts:
                sums.append(hashlib.md5(path.read_bytes()).hexdigest()+'  '+str(path.relative_to(tree)))
        (tree/'DEBIAN/md5sums').write_text('\n'.join(sums)+'\n')
        dest=cache/('nwg-hello_'+record['version']+'_amd64.deb')
        run(['dpkg-deb','--root-owner-group','--build',tree,dest],env=dict(os.environ,SOURCE_DATE_EPOCH=str(EPOCH)))
        extracted=cache/'audited-root'
        run(['dpkg-deb','--extract',dest,extracted])
    return dest


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path)
    p.add_argument('--cache',type=Path,default=Path(__file__).resolve().parents[1]/'.cache/greeter')
    a=p.parse_args()
    print(build(Path(__file__).resolve().parents[1],a.cache,a.base))
