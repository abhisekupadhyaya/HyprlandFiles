"""Stage checksum-locked TUI tools for the unprivileged desktop account."""
import json
import os
from pathlib import Path
import shutil
import tarfile
import zipfile

from hflib import checked_download, operation, run

TUI_PACKAGES = (
    'bluez', 'rfkill', 'file', 'ffmpeg', 'poppler-utils', '7zip', 'tmux', 'btop',
    'cargo', 'gcc', 'pkg-config', 'libclang-dev', 'libpipewire-0.3-dev',
)
PROGRAMS = ('yazi', 'ya', 'spf', 'bluetui', 'wiremix', '.wiremix-bin')


def locked_sources(root):
    return json.loads((root/'locks/tui-amd64.json').read_text())


def preflight(home, managed, adopt):
    """Catch user binary conflicts before beginning the system install."""
    from hflib import fingerprint, no_symlink_parents
    for name in PROGRAMS:
        path = home/'.local/bin'/name
        no_symlink_parents(path, home)
        before = fingerprint(path)
        if before not in ('absent', managed.get(str(path))) and not adopt:
            raise ValueError('Existing terminal tool; back it up or use --adopt: '+str(path))


def install_operations(root, home, workdir):
    if os.geteuid() == 0:
        raise ValueError('Build and install terminal tools as the desktop account')
    sources = {
        item['name']: checked_download(item['url'], item['sha256'], workdir/item['filename'])
        for item in locked_sources(root)
    }
    programs = {}
    with zipfile.ZipFile(sources['Yazi']) as archive:
        for name in ('yazi', 'ya'):
            programs[name] = archive.read('yazi-x86_64-unknown-linux-gnu/'+name)
    with tarfile.open(sources['Superfile']) as archive:
        member = next(m for m in archive.getmembers() if Path(m.name).name == 'spf' and m.isfile())
        with archive.extractfile(member) as executable:
            programs['spf'] = executable.read()
    programs['bluetui'] = sources['Bluetui'].read_bytes()

    with tarfile.open(sources['Wiremix']) as archive:
        archive.extractall(workdir, filter='data')
    source = workdir/sources['Wiremix'].stem
    cargo = shutil.which('cargo', path='/usr/bin:/bin')
    if cargo is None:
        raise RuntimeError('Ubuntu Cargo is required for Wiremix. Complete the system install first.')
    env = dict(os.environ, CARGO_HOME=str(workdir/'cargo'), CARGO_TARGET_DIR=str(workdir/'target'), CC='/usr/bin/gcc')
    run([cargo, 'build', '--manifest-path', source/'Cargo.toml', '--release', '--locked', '--jobs', '2'], env=env, cwd=source)
    programs['.wiremix-bin'] = (workdir/'target/release/wiremix').read_bytes()
    programs['wiremix'] = (root/'tools/wiremix-launcher.sh').read_bytes()
    return [operation(home/'.local/bin'/name, programs[name], 0o755) for name in PROGRAMS]
