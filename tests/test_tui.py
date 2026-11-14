"""Terminal payloads, offline Cargo builds and retained registry inputs; no real build."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from hflib import Transaction, fingerprint, managed_state
import prepare_tui
import tui

ROOT=Path(__file__).resolve().parents[1]


def archive(path,files):
    with tarfile.open(path,'w') as stream:
        for name,data in files.items():
            info=tarfile.TarInfo(name);info.size=len(data)
            stream.addfile(info,io.BytesIO(data))


class TerminalTools(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name);self.root=self.base/'repo';self.home=self.base/'home';self.work=self.base/'work'
        for directory in (self.root/'tools',self.root/'locks',self.home,self.work):directory.mkdir(parents=True)
        (self.root/'tools/wiremix-launcher.sh').write_bytes((ROOT/'tools/wiremix-launcher.sh').read_bytes())
        self.records=[];self.artifacts={}
        for name,filename in [('Yazi','yazi.zip'),('Superfile','spf.tar'),('Bluetui','bluetui'),('Wiremix','wiremix-1.crate')]:
            path=self.base/filename
            if name=='Yazi':
                with zipfile.ZipFile(path,'w') as stream:
                    for executable in ('yazi','ya'):stream.writestr('yazi-x86_64-unknown-linux-gnu/'+executable,executable.encode())
            elif name=='Superfile':archive(path,{'release/spf':b'spf'})
            elif name=='Wiremix':archive(path,{'wiremix-1/Cargo.toml':b'[package]\nname="wiremix"\nversion="1.0.0"\n'})
            else:path.write_bytes(b'bluetui')
            self.records.append(dict(name=name,filename=filename,sha256=prepare_tui.digest(path),url='https://example.invalid/'+filename))
            self.artifacts[('tui',name)]=path
        vendor=self.base/'vendor.tar';archive(vendor,{'dependency-1/Cargo.toml':b'fixture'})
        self.records[-1]['vendor']=dict(filename=vendor.name,sha256=prepare_tui.digest(vendor),size=vendor.stat().st_size)
        self.artifacts[('tui-vendor','Wiremix')]=vendor
        self.save_lock()
        patches=[patch.object(tui.os,'geteuid',return_value=1000),patch.object(tui.shutil,'which',return_value='/usr/bin/cargo')]
        for item in patches:item.start();self.addCleanup(item.stop)

    def save_lock(self):
        (self.root/'locks/tui-amd64.json').write_text(json.dumps(self.records))

    def compile(self,argv,env,cwd):
        self.assertIn('--frozen',argv)
        config=(Path(env['CARGO_HOME'])/'config.toml').read_text()
        self.assertIn('offline = true',config)
        self.assertIn('replace-with = "vendored-sources"',config)
        self.assertTrue((Path(cwd)/'Cargo.toml').is_file())
        executable=Path(env['CARGO_TARGET_DIR'])/'release/wiremix'
        executable.parent.mkdir(parents=True);executable.write_bytes(b'compiled-fixture')

    def test_kit_path_never_downloads_and_payload_rolls_back(self):
        target=self.home/'.local/bin/yazi';target.parent.mkdir(parents=True)
        target.write_bytes(b'personal-yazi');target.chmod(0o750);original=fingerprint(target)
        with patch.object(tui,'checked_download',side_effect=AssertionError('kit must not download')), \
                patch.object(tui,'prepare_vendor',side_effect=AssertionError('kit must not regenerate dependencies')), \
                patch.object(tui,'run',side_effect=self.compile):
            operations=tui.install_operations(self.root,self.home,self.work,self.artifacts)
        store=self.home/'backups';tx=Transaction(store,self.home)
        snapshot=tx.apply(operations,adopt=True)
        for name in tui.PROGRAMS:self.assertTrue(os.access(self.home/'.local/bin'/name,os.X_OK))
        self.assertIsNone(Transaction(store,self.home,managed_state(store)).apply(operations))
        tx.rollback(snapshot)
        self.assertEqual(fingerprint(target),original)
        self.assertFalse((self.home/'.local/bin/wiremix').exists())

    def test_modified_and_missing_kit_inputs_fail_before_build(self):
        self.artifacts[('tui','Bluetui')].write_bytes(b'tampered')
        with patch.object(tui,'run') as run:
            with self.assertRaisesRegex(ValueError,'Bluetui'):tui.install_operations(self.root,self.home,self.work,self.artifacts)
            run.assert_not_called()
        self.artifacts.pop(('tui','Yazi'))
        with self.assertRaisesRegex(ValueError,'Yazi'):tui.install_operations(self.root,self.home,self.work,self.artifacts)

    def test_online_path_prepares_the_same_locked_vendor_inputs(self):
        def download(url,checksum,destination):
            return next(path for (kind,name),path in self.artifacts.items()
                        if kind=='tui' and path.name==Path(destination).name)
        with patch.object(tui,'checked_download',side_effect=download), \
                patch.object(tui,'prepare_vendor',return_value=self.artifacts[('tui-vendor','Wiremix')]) as prepare, \
                patch.object(tui,'run',side_effect=self.compile):
            ops=tui.install_operations(self.root,self.home,self.work)
        prepare.assert_called_once_with(self.records[-1],self.artifacts[('tui','Wiremix')],self.work)
        self.assertEqual(next(op['data'] for op in ops if op['path'].endswith('/.wiremix-bin')),b'compiled-fixture')

    def test_tampered_vendor_input_is_rejected_before_build(self):
        self.artifacts[('tui-vendor','Wiremix')].write_bytes(b'tampered')
        with patch.object(tui,'run') as run:
            with self.assertRaisesRegex(ValueError,'Wiremix'):tui.install_operations(self.root,self.home,self.work,self.artifacts)
            run.assert_not_called()

    def test_build_failure_does_not_install_partial_tools(self):
        with patch.object(tui,'run',side_effect=subprocess.CalledProcessError(1,['cargo'])):
            with self.assertRaises(subprocess.CalledProcessError):tui.install_operations(self.root,self.home,self.work,self.artifacts)
        self.assertFalse((self.home/'.local/bin').exists())

    def test_root_build_and_missing_cargo_are_refused(self):
        with patch.object(tui.os,'geteuid',return_value=0):
            with self.assertRaises(ValueError):tui.install_operations(self.root,self.home,self.work,self.artifacts)
        with patch.object(tui.shutil,'which',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'Cargo'):tui.install_operations(self.root,self.home,self.work,self.artifacts)

    def test_conflicts_and_edited_managed_binaries_are_detected(self):
        target=self.home/'.local/bin/yazi';target.parent.mkdir(parents=True);target.write_bytes(b'old')
        before=fingerprint(target)
        with self.assertRaises(ValueError):tui.preflight(self.home,{},False)
        tui.preflight(self.home,{str(target):before},False)
        target.write_bytes(b'edited')
        with self.assertRaises(ValueError):tui.preflight(self.home,{str(target):before},False)
        tui.preflight(self.home,{},True)

    def test_unsafe_wiremix_archive_cannot_escape_workspace(self):
        path=self.artifacts[('tui','Wiremix')];archive(path,{'../escaped':b'bad'})
        self.records[-1]['sha256']=prepare_tui.digest(path);self.save_lock()
        with self.assertRaisesRegex(ValueError,'Unsafe'):tui.install_operations(self.root,self.home,self.work,self.artifacts)
        self.assertFalse((self.base/'escaped').exists())


class RegistryInputs(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name);self.cache=self.base/'cache';(self.cache/'crates').mkdir(parents=True)
        dependency=self.cache/'crates/dependency-1.0.0.crate'
        archive(dependency,{'dependency-1.0.0/Cargo.toml':b'[package]\nname="dependency"\nversion="1.0.0"\n'})
        self.checksum=prepare_tui.digest(dependency)
        self.crate=self.base/'wiremix-1.crate'
        lock='''version = 3
[[package]]
name = "wiremix"
version = "1.0.0"
[[package]]
name = "dependency"
version = "1.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "'''+self.checksum+'"\n'
        self.lock=lock
        archive(self.crate,{'wiremix-1/Cargo.lock':lock.encode()})

    def test_cached_crates_produce_identical_vendor_archives_without_network(self):
        a,b=self.base/'a.tar',self.base/'b.tar'
        with patch('urllib.request.urlopen',side_effect=AssertionError('verified cache must be sufficient')):
            self.assertEqual(prepare_tui.build_vendor(self.crate,self.cache,a),1)
            prepare_tui.build_vendor(self.crate,self.cache,b)
        self.assertEqual(a.read_bytes(),b.read_bytes())
        with tarfile.open(a) as stream:
            checksums=json.load(stream.extractfile('dependency-1.0.0/.cargo-checksum.json'))
            self.assertEqual(checksums['package'],self.checksum)
            data=stream.extractfile('dependency-1.0.0/Cargo.toml').read()
            self.assertEqual(checksums['files']['Cargo.toml'],hashlib.sha256(data).hexdigest())

    def test_unreviewed_vendor_hash_is_rejected(self):
        record={'vendor':dict(filename='vendor.tar',sha256='0'*64,size=0)}
        with self.assertRaisesRegex(ValueError,'differ from the reviewed'):
            prepare_tui.prepare_vendor(record,self.crate,self.cache)
        self.assertFalse((self.cache/'vendor.tar').exists())

    def test_non_registry_sources_are_refused(self):
        lock=self.lock.replace('registry+https://github.com/rust-lang/crates.io-index','git+https://example.invalid/unreviewed')
        archive(self.crate,{'wiremix-1/Cargo.lock':lock.encode()})
        with self.assertRaisesRegex(ValueError,'Only locked crates.io'):prepare_tui.dependencies(self.crate)

    def test_source_archive_links_are_refused(self):
        path=self.base/'link.tar'
        with tarfile.open(path,'w') as stream:
            info=tarfile.TarInfo('redirect');info.type=tarfile.SYMTYPE;info.linkname='/tmp'
            stream.addfile(info)
        with tarfile.open(path) as stream:
            with self.assertRaisesRegex(ValueError,'Unsafe'):prepare_tui.extract(stream,self.base/'extract')


class AudioLauncher(unittest.TestCase):
    def test_ssh_runtime_fallback_and_explicit_runtime_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory);program=home/'.local/bin/.wiremix-bin'
            program.parent.mkdir(parents=True)
            program.write_text('#!/bin/sh\nprintf "%s" "${PIPEWIRE_RUNTIME_DIR:-unset}"\n');program.chmod(0o755)
            env=dict(os.environ,HOME=str(home))
            env.pop('XDG_RUNTIME_DIR',None);env.pop('PIPEWIRE_RUNTIME_DIR',None)
            command=['sh',str(ROOT/'tools/wiremix-launcher.sh')]
            self.assertEqual(subprocess.check_output(command,env=env,text=True),'/run/user/'+str(os.getuid()))
            env['PIPEWIRE_RUNTIME_DIR']=str(home/'explicit-runtime')
            self.assertEqual(subprocess.check_output(command,env=env,text=True),env['PIPEWIRE_RUNTIME_DIR'])
            env.pop('PIPEWIRE_RUNTIME_DIR');env['XDG_RUNTIME_DIR']=str(home/'xdg-runtime')
            self.assertEqual(subprocess.check_output(command,env=env,text=True),'unset')
