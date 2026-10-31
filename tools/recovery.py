"""Preserve locked desktop artifacts independently of live PPA availability.

The checked-in manifest is the trust anchor. A manifest shipped inside a kit is
never accepted as its own authority. Ordinary Ubuntu dependencies/security updates
still come from the target machine's signed Ubuntu sources.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from hflib import no_symlink_parents, output

MANIFEST = 'locks/recovery-ubuntu-26.04-amd64.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def package_info(path):
    fields = output(['dpkg-deb','-f',path,'Package','Version','Architecture'])
    return dict(line.split(': ',1) for line in fields.splitlines() if ': ' in line)


def verify(root, directory):
    root, directory = Path(root), Path(directory).absolute()
    trusted = root / MANIFEST
    expected = json.loads(trusted.read_text())
    lock = json.loads((root/'locks/ubuntu-26.04-amd64.json').read_text())
    if expected.get('schema') != 1 or expected.get('target') != 'ubuntu-26.04-amd64':
        raise ValueError('Unknown recovery manifest format or target')
    if expected['lock_sha256'] != digest(root/'locks/ubuntu-26.04-amd64.json') or expected['patch_sha256'] != digest(root/'patches/nwg-hello-0.4.2-privacy-and-ipc.patch'):
        raise ValueError('Recovery manifest is stale for this checkout')
    no_symlink_parents(directory/'manifest.json',directory.parent)
    if (directory/'manifest.json').is_symlink() or digest(directory/'manifest.json') != digest(trusted):
        raise ValueError('Kit manifest differs from the reviewed Git manifest')
    paths = {}
    for item in expected['artifacts']:
        relative = Path(item['file'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe artifact path')
        path = directory/relative
        no_symlink_parents(path,directory)
        if path.is_symlink() or not path.is_file() or path.stat().st_size != item['size'] or digest(path) != item['sha256']:
            raise ValueError('Recovery artifact missing or modified: '+str(relative))
        key = (item['kind'],item['name'])
        if key in paths:
            raise ValueError('Duplicate recovery artifact')
        if item['kind'] in ('package','greeter','source'):
            actual=package_info(path)
            if (actual.get('Package'),actual.get('Version'),actual.get('Architecture')) != (item['name'],item['version'],item['architecture']):
                raise ValueError('Package identity mismatch: '+str(relative))
        paths[key] = path
    packages={x['name']:x['version'] for x in expected['artifacts'] if x['kind']=='package'}
    if packages != lock['packages']:
        raise ValueError('Recovery kit does not cover the exact desktop package lock')
    greeter=next((x for x in expected['artifacts'] if x['kind']=='greeter'),{})
    if greeter.get('version') != lock['nwg_hello']['version'] or greeter.get('name')!='nwg-hello':
        raise ValueError('Patched greeter missing from kit')
    for wheel in json.loads((root/'locks/python-wheels.json').read_text()):
        path=paths.get(('wheel',wheel['filename']))
        if not path or digest(path)!=wheel['sha256']:
            raise ValueError('Locked palette wheel missing from kit')
    return paths


def apt_record(name, version, sha256):
    for block in output(['apt-cache','show',name+'='+version]).split('\n\n'):
        fields=dict(x.split(': ',1) for x in block.splitlines() if ': ' in x and not x.startswith(' '))
        if fields.get('Version')==version and fields.get('SHA256')==sha256 and fields.get('Filename'):
            return fields
    raise ValueError('Archive does not match a SHA256 in the installed signed APT metadata: '+name)


def create(root, destination, archive_dirs, write_manifest=False):
    """Maintainer release operation; no install, root, daemon or system writes."""
    root, destination = Path(root), Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('Use a new kit directory; existing artifacts are never overwritten')
    lock=json.loads((root/'locks/ubuntu-26.04-amd64.json').read_text())
    candidates={}
    for directory in archive_dirs:
        for path in Path(directory).rglob('*.deb'):
            info=package_info(path)
            candidates.setdefault((info.get('Package'),info.get('Version')),path)
    entries=[];sources={}
    def add(kind,name,path,relative,version=None,architecture=None,url=None):
        entry=dict(kind=kind,name=name,file=relative,sha256=digest(path),size=path.stat().st_size)
        if version is not None: entry.update(version=version,architecture=architecture)
        if url: entry['source_url']=url
        entries.append(entry);sources[relative]=path
    for name,version in sorted(lock['packages'].items()):
        path=candidates.get((name,version))
        if not path:
            raise ValueError('Missing archive; retrieve with apt-get download '+name+'='+version)
        record=apt_record(name,version,digest(path));info=package_info(path)
        base='https://ppa.launchpadcontent.net/cppiber/hyprland/ubuntu/' if name in lock['ppa_packages'] else 'https://archive.ubuntu.com/ubuntu/'
        add('package',name,path,'packages/'+Path(record['Filename']).name,version,info['Architecture'],base+record['Filename'])
    patched=candidates.get(('nwg-hello',lock['nwg_hello']['version']))
    expected=json.loads((root/'docs/release-preparation.json').read_text())['greeter_build']['sha256']
    if not patched or digest(patched)!=expected:
        raise ValueError('Build and verify the reviewed patched greeter first')
    add('greeter','nwg-hello',patched,'packages/nwg-hello_'+lock['nwg_hello']['version']+'_amd64.deb',lock['nwg_hello']['version'],'amd64')
    original=candidates.get(('nwg-hello',lock['nwg_hello']['base_version']))
    if not original or digest(original)!=lock['nwg_hello']['sha256']:
        raise ValueError('Verified original greeter archive missing')
    add('source','nwg-hello',original,'sources/nwg-hello-original.deb',lock['nwg_hello']['base_version'],'amd64',lock['nwg_hello']['url'])
    for wheel in json.loads((root/'locks/python-wheels.json').read_text()):
        matches=[p for directory in archive_dirs for p in Path(directory).rglob(wheel['filename']) if p.is_file() and digest(p)==wheel['sha256']]
        if not matches:
            raise ValueError('Missing verified wheel: '+wheel['filename'])
        add('wheel',wheel['filename'],matches[0],'wheels/'+wheel['filename'],url=wheel['url'])
    manifest=dict(schema=1,target='ubuntu-26.04-amd64',lock_sha256=digest(root/'locks/ubuntu-26.04-amd64.json'),patch_sha256=digest(root/'patches/nwg-hello-0.4.2-privacy-and-ipc.patch'),artifacts=sorted(entries,key=lambda x:x['file']))
    encoded=json.dumps(manifest,indent=2)+'\n'
    if not write_manifest and (root/MANIFEST).read_text()!=encoded:
        raise ValueError('Artifacts differ from the committed release manifest; review a new manifest explicitly')
    destination.mkdir(parents=True,mode=0o700)
    for relative,source in sources.items():
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
    (destination/'manifest.json').write_text(encoded)
    if write_manifest:
        (root/MANIFEST).write_text(encoded)
    verify(root,destination)
    return manifest


def package(root, directory, archive):
    """Source + verified kit, with a deterministic layout and no host state."""
    root, directory, archive = Path(root), Path(directory), Path(archive)
    verify(root,directory)
    if archive.exists() or archive.is_symlink():
        raise ValueError('Use a new archive filename; never overwrite a retained release')
    sys.path.insert(0,str(root/'scripts'))
    from audit_public import public_files
    files=[(p,'HyprlandFiles/'+p.relative_to(root).as_posix()) for p in public_files(root)]
    for path,_ in files:
        if path.name.startswith('.env') or path.suffix.lower() in ('.key','.pem','.deb','.whl','.log','.gz','.zip'):
            raise ValueError('Private/local artifact is not release source: '+str(path.relative_to(root)))
    manifest=json.loads((root/MANIFEST).read_text())
    for relative in ['manifest.json',*[x['file'] for x in manifest['artifacts']]]:
        files.append((directory/relative,'HyprlandFiles/bundles/ubuntu-26.04-amd64/'+relative))
    archive.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation: a failed packaging attempt leaves a visibly incomplete
    # archive to inspect, never overwrites an existing known-good backup.
    with archive.open('xb') as target:
        with gzip.GzipFile(filename='',mode='wb',fileobj=target,mtime=0) as compressed:
            with tarfile.open(fileobj=compressed,mode='w|') as stream:
                for path,name in sorted(files,key=lambda x:x[1]):
                    if path.is_symlink(): raise ValueError('Release source symlink refused')
                    info=tarfile.TarInfo(name)
                    info.size=path.stat().st_size;info.mtime=1793383200
                    info.mode=0o755 if path.stat().st_mode & 0o111 else 0o644
                    with path.open('rb') as content:stream.addfile(info,content)
    return digest(archive)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('create','verify','package'))
    parser.add_argument('directory',type=Path)
    parser.add_argument('archive',nargs='?',type=Path)
    parser.add_argument('--archive-dir',type=Path,action='append',default=[])
    parser.add_argument('--write-manifest',action='store_true',help='Maintainer-only: explicitly update the Git trust anchor for review')
    a=parser.parse_args();root=Path(__file__).resolve().parents[1]
    if a.action=='verify':
        print('Verified '+str(len(verify(root,a.directory)))+' recovery artifacts against the Git manifest')
    elif a.action=='create':
        manifest=create(root,a.directory,a.archive_dir,a.write_manifest)
        print('Created verified kit: '+str(a.directory)+' ('+str(len(manifest['artifacts']))+' artifacts)')
    else:
        if not a.archive:parser.error('package needs an output archive filename')
        print(package(root,a.directory,a.archive)+'  '+str(a.archive))
