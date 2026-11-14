#!/usr/bin/python3
"""Cache locked TUI inputs and a deterministic Wiremix dependency archive; no install."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import tarfile
import tempfile
import tomllib

from hflib import atomic, checked_download


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def extract(archive, directory):
    """No archive links, special files, absolute paths or directory traversal."""
    members=archive.getmembers()
    if sum(m.size for m in members)>800_000_000:
        raise ValueError('Terminal source archive exceeds extraction limit')
    for member in members:
        path=Path(member.name)
        if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):
            raise ValueError('Unsafe terminal source archive member: '+member.name)
    archive.extractall(directory,members=members,filter='data')


def dependencies(crate):
    with tarfile.open(crate) as archive:
        member=archive.getmember(Path(crate).stem+'/Cargo.lock')
        if not member.isfile() or member.size>10_000_000:
            raise ValueError('Invalid Wiremix Cargo lockfile')
        with archive.extractfile(member) as stream:
            lock=tomllib.loads(stream.read().decode())
    result=[];seen=set()
    for item in lock['package']:
        if not item.get('source'):
            continue
        if item['source']!='registry+https://github.com/rust-lang/crates.io-index':
            raise ValueError('Only locked crates.io dependencies can be retained')
        name,version,checksum=item['name'],item['version'],item.get('checksum','')
        if (not re.fullmatch(r'[A-Za-z0-9_-]+',name)
                or not re.fullmatch(r'[0-9][A-Za-z0-9.+-]*',version)
                or not re.fullmatch(r'[a-f0-9]{64}',checksum) or (name,version) in seen):
            raise ValueError('Invalid or duplicate Cargo dependency')
        seen.add((name,version))
        result.append(dict(name=name,version=version,sha256=checksum))
    return sorted(result,key=lambda x:(x['name'],x['version']))


def build_vendor(crate, cache, destination):
    """Verify every registry crate against Cargo.lock before producing vendor data."""
    cache,destination=Path(cache),Path(destination)
    records=dependencies(crate)
    def download(item):
        name,version=item['name'],item['version']
        filename=name+'-'+version+'.crate'
        return checked_download('https://static.crates.io/crates/'+name+'/'+filename,
                                item['sha256'],cache/'crates'/filename)
    with ThreadPoolExecutor(max_workers=6) as pool:
        archives=list(pool.map(download,records))
    with tempfile.TemporaryDirectory(prefix='vendor-',dir=cache) as directory:
        vendor=Path(directory)
        for item,path in zip(records,archives):
            prefix=item['name']+'-'+item['version']
            with tarfile.open(path) as archive:
                if any(not Path(m.name).parts or Path(m.name).parts[0]!=prefix for m in archive.getmembers()):
                    raise ValueError('Cargo archive has an unexpected root')
                extract(archive,vendor)
            package=vendor/prefix
            files={p.relative_to(package).as_posix():digest(p) for p in sorted(package.rglob('*'))
                   if p.is_file() and p.name!='.cargo-checksum.json'}
            atomic(package/'.cargo-checksum.json',json.dumps(dict(files=files,package=item['sha256']),sort_keys=True)+'\n')
        # Uncompressed tar avoids differing zlib releases changing the trust hash.
        with tarfile.open(destination,'w',format=tarfile.USTAR_FORMAT) as stream:
            for path in sorted(vendor.rglob('*')):
                if not path.is_file():
                    continue
                info=tarfile.TarInfo(path.relative_to(vendor).as_posix())
                info.size=path.stat().st_size
                info.mode=0o755 if path.stat().st_mode & 0o111 else 0o644
                with path.open('rb') as content:
                    stream.addfile(info,content)
    return len(records)


def prepare_vendor(record, crate, cache, refresh=False):
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    vendor=record['vendor'];target=cache/vendor['filename']
    if target.is_symlink():
        raise ValueError('Vendor archive must be a regular file')
    if not refresh and target.is_file() and digest(target)==vendor['sha256']:
        return target
    with tempfile.TemporaryDirectory(prefix='prepare-vendor-',dir=cache) as directory:
        staged=Path(directory)/vendor['filename']
        count=build_vendor(crate,cache,staged)
        checksum=digest(staged)
        if not refresh and (checksum!=vendor['sha256'] or staged.stat().st_size!=vendor['size']):
            raise ValueError('Regenerated Wiremix dependencies differ from the reviewed vendor lock')
        if refresh:
            vendor.update(sha256=checksum,size=staged.stat().st_size,crates=count)
        os.replace(staged,target)
    return target


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path)
    parser.add_argument('--write-vendor-lock',action='store_true',help='Maintainer: record actual verified vendor archive hash for review')
    a=parser.parse_args();root=Path(__file__).resolve().parents[1]
    cache=a.cache or root/'.cache/tui';cache.mkdir(parents=True,exist_ok=True)
    lock=root/'locks/tui-amd64.json';records=json.loads(lock.read_text())
    sources={item['name']:checked_download(item['url'],item['sha256'],cache/item['filename']) for item in records}
    record=next(item for item in records if item['name']=='Wiremix')
    print('Preparing checksum-locked Wiremix registry dependencies',flush=True)
    archive=prepare_vendor(record,sources['Wiremix'],cache,a.write_vendor_lock)
    if a.write_vendor_lock:
        atomic(lock,json.dumps(records,indent=2)+'\n')
    print('Verified four terminal inputs and '+str(record['vendor']['crates'])+' retained crates: '+str(archive))


if __name__=='__main__':
    main()
