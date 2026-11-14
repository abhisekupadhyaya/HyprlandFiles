"""Stage checksum-locked TUI tools for the unprivileged desktop account."""
import json
import os
from pathlib import Path
import shutil
import tarfile
import zipfile

from hflib import checked_download, operation, run
from prepare_tui import digest, extract, prepare_vendor

TUI_PACKAGES = (
    'bluez', 'rfkill', 'file', 'ffmpeg', 'poppler-utils', '7zip', 'tmux', 'btop', 'xdg-utils',
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


def install_operations(root, home, workdir, artifacts=None):
    if os.geteuid() == 0:
        raise ValueError('Build and install terminal tools as the desktop account')
    records=locked_sources(root)
    def input_path(item,kind='tui'):
        if artifacts is None:
            return checked_download(item['url'],item['sha256'],workdir/item['filename'])
        path=artifacts.get((kind,item['name']))
        if path is None or Path(path).is_symlink() or digest(path)!=item['sha256']:
            raise ValueError('Verified terminal input missing or modified: '+item['name'])
        return Path(path)
    sources={item['name']:input_path(item) for item in records}
    wiremix=next(item for item in records if item['name']=='Wiremix')
    if artifacts is None:
        vendor=prepare_vendor(wiremix,sources['Wiremix'],workdir)
    else:
        vendor=input_path(dict(wiremix['vendor'],name='Wiremix'),kind='tui-vendor')
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
        extract(archive,workdir)
    vendor_dir=workdir/'vendor';vendor_dir.mkdir()
    with tarfile.open(vendor) as archive:
        extract(archive,vendor_dir)
    source = workdir/sources['Wiremix'].stem
    cargo = shutil.which('cargo', path='/usr/bin:/bin')
    if cargo is None:
        raise RuntimeError('Ubuntu Cargo is required for Wiremix. Complete the system install first.')
    cargo_home=workdir/'cargo';cargo_home.mkdir()
    (cargo_home/'config.toml').write_text('[source.crates-io]\nreplace-with = "vendored-sources"\n'
        '[source.vendored-sources]\ndirectory = '+json.dumps(str(vendor_dir))+'\n[net]\noffline = true\n')
    env = dict(os.environ, CARGO_HOME=str(cargo_home), CARGO_TARGET_DIR=str(workdir/'target'), CC='/usr/bin/gcc')
    run([cargo, 'build', '--manifest-path', source/'Cargo.toml', '--release', '--frozen', '--jobs', '2'], env=env, cwd=source)
    programs['.wiremix-bin'] = (workdir/'target/release/wiremix').read_bytes()
    programs['wiremix'] = (root/'tools/wiremix-launcher.sh').read_bytes()
    return [operation(home/'.local/bin'/name, programs[name], 0o755) for name in PROGRAMS]
