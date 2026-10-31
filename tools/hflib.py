"""Installer primitives. Standard library only; no host mutations on import."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.request
import zipfile

VERSION = "0.1.0-rc.2"
PREFIX = Path("/usr/local/share/hyprlandfiles")
ROOT_STATE = Path("/var/lib/hyprlandfiles")


def run(argv, **kwargs):
    return subprocess.run([str(x) for x in argv], check=True, **kwargs)


def output(argv):
    return run(argv, text=True, capture_output=True).stdout.strip()


def atomic(path, data, mode=0o644):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".hf-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data if isinstance(data, bytes) else data.encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if os.path.lexists(name):
            os.unlink(name)


def fingerprint(path):
    path = Path(path)
    if path.is_symlink():
        return "link:" + os.readlink(path)
    if not path.exists():
        return "absent"
    if not path.is_file():
        raise ValueError("Expected a regular file or symlink: " + str(path))
    s = path.stat()
    return "file:" + hashlib.sha256(path.read_bytes()).hexdigest() + f":{stat.S_IMODE(s.st_mode):o}:{s.st_uid}:{s.st_gid}"


def no_symlink_parents(path, boundary):
    """Refuse redirecting config writes through an unrelated symlink directory."""
    if '..' in Path(path).parts or '..' in Path(boundary).parts:
        raise ValueError('Parent traversal is not an installation target')
    path, boundary = Path(path).absolute(), Path(boundary).absolute()
    if not path.is_relative_to(boundary) or path == boundary:
        raise ValueError("Target escapes installation boundary: " + str(path))
    for parent in path.parents:
        if parent.is_symlink():
            raise ValueError("Symlink parent requires manual review: " + str(parent))
        if parent == boundary:
            break


def operation(path, data=None, mode=0o644, link=None, remove=False):
    return dict(path=str(path), data=data, mode=mode, link=link, remove=remove)


class Transaction:
    """Per-file cp -a snapshots, write-ahead journal, strict rollback conflicts.

    Directory creation is retained on rollback; packages are never auto-removed.
    Root and user transactions use separate private stores and ownership.
    """

    def __init__(self, store, boundary, managed=None):
        self.store, self.boundary = Path(store), Path(boundary)
        self.managed = managed or {}

    def apply(self, operations, adopt=False, dry_run=False, show_rollback=True):
        if len({x['path'] for x in operations}) != len(operations):
            raise ValueError("Duplicate transaction target")
        entries = []
        for op in operations:
            p = Path(op['path'])
            no_symlink_parents(p, self.boundary)
            before = fingerprint(p)
            if op['remove']:
                after = 'absent'
            elif op['link'] is not None:
                after = 'link:' + op['link']
            else:
                data = op['data'] if isinstance(op['data'], bytes) else op['data'].encode()
                after = 'file:' + hashlib.sha256(data).hexdigest() + f":{op['mode']:o}:{os.getuid()}:{os.getgid()}"
            if before == after:
                continue
            expected = self.managed.get(str(p))
            if before != 'absent' and before != expected and not adopt:
                raise ValueError("Existing or edited file; merge it or explicitly use --adopt (backs it up): " + str(p))
            if expected and before not in (expected, 'absent') and not adopt:
                raise ValueError("Unrelated edit: " + str(p))
            entries.append(dict(path=str(p), before=before, after=after))
        if dry_run:
            return entries
        if not entries:
            return None
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        no_symlink_parents(self.store / "manifest-probe", self.store.parent.parent)
        self.store.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.store.is_symlink() or self.store.stat().st_uid != os.getuid():
            raise ValueError("Unsafe backup store")
        os.chmod(self.store, 0o700)
        snapshot = self.store / stamp
        snapshot.mkdir(mode=0o700)
        for i, entry in enumerate(entries):
            if entry['before'] != 'absent':
                run(['cp', '-a', '--', entry['path'], snapshot / str(i)])
        journal = dict(schema=1, uid=os.getuid(), boundary=str(self.boundary), status='prepared', entries=entries)
        atomic(snapshot / 'manifest.json', json.dumps(journal, indent=2)+'\n', 0o600)
        print("BACKUP=" + str(snapshot), flush=True)
        if show_rollback:
            print("Rollback: ./install.sh rollback " + str(snapshot), flush=True)
        index = {x['path']: x for x in operations}
        for entry in entries:
            p = Path(entry['path'])
            no_symlink_parents(p, self.boundary)
            if fingerprint(p) != entry['before']:
                raise ValueError("Target changed during installation: " + str(p))
            op = index[str(p)]
            if op['remove']:
                p.unlink(missing_ok=True)
            elif op['link'] is not None:
                p.parent.mkdir(parents=True, exist_ok=True)
                temporary = p.with_name('.' + p.name + '.hf-link')
                if temporary.exists() or temporary.is_symlink():
                    raise ValueError("Unrelated temporary path exists: " + str(temporary))
                temporary.symlink_to(op['link'])
                os.replace(temporary, p)
            else:
                atomic(p, op['data'], op['mode'])
        journal['status'] = 'complete'
        atomic(snapshot / 'manifest.json', json.dumps(journal, indent=2)+'\n', 0o600)
        return snapshot

    def rollback(self, snapshot):
        snapshot = Path(snapshot).absolute()
        if snapshot.is_symlink() or not snapshot.is_relative_to(self.store.absolute()):
            raise ValueError("Use an exact snapshot inside the backup store")
        no_symlink_parents(snapshot / 'manifest.json', self.store)
        manifest = snapshot / 'manifest.json'
        if manifest.is_symlink() or manifest.stat().st_uid != os.getuid():
            raise ValueError("Snapshot owner mismatch")
        journal = json.loads(manifest.read_text())
        if journal['uid'] != os.getuid() or journal['boundary'] != str(self.boundary):
            raise ValueError("Snapshot identity mismatch")
        for entry in journal['entries']:
            p = Path(entry['path'])
            no_symlink_parents(p, self.boundary)
            if fingerprint(p) not in (entry['after'], entry['before']):
                raise ValueError("Edited since installation; refusing rollback: " + str(p))
        for i in reversed(range(len(journal['entries']))):
            entry = journal['entries'][i]
            p = Path(entry['path'])
            if fingerprint(p) == entry['before']:
                continue
            p.unlink(missing_ok=True)
            if entry['before'] != 'absent':
                p.parent.mkdir(parents=True, exist_ok=True)
                run(['cp', '-a', '--', snapshot / str(i), p])
        journal['status'] = 'rolled-back'
        atomic(manifest, json.dumps(journal, indent=2)+'\n', 0o600)


def managed_state(store):
    """Replay complete transactions and undo records without losing history."""
    result = {}
    for path in sorted(Path(store).glob('*/manifest.json')):
        j = json.loads(path.read_text())
        if j['status'] == 'prepared':
            raise ValueError('Interrupted transaction; inspect and rollback first: ' + str(path.parent))
        if j['status'] == 'complete':
            result.update({e['path']: e['after'] for e in j['entries']})
    return result


def os_release(path=Path('/etc/os-release')):
    result = {}
    for line in path.read_text().splitlines():
        if re.match(r'^[A-Z_]+=', line):
            k, v = line.split('=', 1)
            result[k] = v.strip('"\'')
    return result


def require_supported(release, architecture):
    if release.get('ID') != 'ubuntu' or release.get('VERSION_ID') != '26.04' or architecture != 'amd64':
        raise ValueError('This release supports Ubuntu 26.04 amd64 only. No changes made. See docs/compatibility.md.')


def validate_options(profile, scale, gpu, keyboard):
    if profile not in ('desktop', 'laptop-server'):
        raise ValueError('Unknown profile')
    if scale != 'auto' and not (re.fullmatch(r'\d+(\.\d+)?', scale) and 0.5 <= float(scale) <= 4):
        raise ValueError('Scale must be auto or a number from 0.5 to 4')
    if gpu not in ('auto', 'default') and not re.fullmatch(r'[\da-fA-F]{4}:[\da-fA-F]{2}:[\da-fA-F]{2}\.[0-7]', gpu):
        raise ValueError('GPU must be auto, default or a PCI identifier')
    if not re.fullmatch(r'[a-z0-9_,+-]{1,64}', keyboard):
        raise ValueError('Invalid XKB layout list')


def checked_download(url, sha256, destination):
    destination = Path(destination)
    if not re.fullmatch(r'[0-9a-f]{64}', sha256) or not url.startswith('https://'):
        raise ValueError('HTTPS URL and SHA256 are required')
    if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == sha256:
        return destination
    with urllib.request.urlopen(url, timeout=60) as response:
        if not response.geturl().startswith('https://'):
            raise ValueError('Refusing non-HTTPS redirect')
        data = response.read(100_000_001)
    if len(data) > 100_000_000 or hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError('Download checksum/size mismatch: ' + destination.name)
    atomic(destination, data)
    return destination


def extract_wheel(wheel, destination):
    with zipfile.ZipFile(wheel) as archive:
        for item in archive.infolist():
            p = Path(item.filename)
            if p.is_absolute() or '..' in p.parts or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Unsafe wheel path')
        if sum(x.file_size for x in archive.infolist()) > 300_000_000:
            raise ValueError('Wheel exceeds extraction limit')
        archive.extractall(destination)


def reject_apt_removals(simulation):
    if any(line.startswith(('Remv ', 'Purg ')) for line in simulation.splitlines()):
        raise ValueError('APT proposes removals. Resolve manually; no packages installed.')
    if 'WARNING: The following packages cannot be authenticated!' in simulation:
        raise ValueError('APT authentication failed')


def detect_profile(lid_root=Path('/proc/acpi/button/lid')):
    """Choose the supported laptop policy only when ACPI lid hardware exists."""
    return 'laptop-server' if any(lid_root.glob('*/state')) else 'desktop'


def reject_unrelated_changes(simulation, installed, allowed):
    """APT may omit :architecture while dpkg includes it; compare both forms."""
    existing={name.split(':',1)[0] for name in installed}
    for line in simulation.splitlines():
        parts=line.split()
        if len(parts)>1 and parts[0]=='Inst':
            name=parts[1].split(':',1)[0]
            if name in existing and name not in allowed:
                raise ValueError('APT would change an existing unrelated package: '+name+'. Update Ubuntu separately, then retry.')
