"""Recovery kit verification against a separate Git trust anchor; no host install."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
import tarfile
from unittest.mock import patch
from hflib import detect_profile, reject_unrelated_changes
import recovery


class Recovery(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/'repo';self.cache=self.base/'cache';self.cache.mkdir()
        for folder in ('locks','patches','docs'):(self.root/folder).mkdir(parents=True)
        lock={'packages':{'example':'1'},'ppa_packages':[],
              'nwg_hello':{'version':'0.4.2-1+hf1','base_version':'0.4.2-1','sha256':'','url':'https://example.invalid/base.deb'}}
        example=self.package('example','1');self.original=self.package('nwg-hello','0.4.2-1');patched=self.package('nwg-hello','0.4.2-1+hf1')
        lock['nwg_hello']['sha256']=recovery.digest(self.original)
        (self.root/'locks/ubuntu-26.04-amd64.json').write_text(json.dumps(lock))
        (self.root/'patches/nwg-hello-0.4.2-privacy-and-ipc.patch').write_text('reviewed patch fixture\n')
        (self.root/'docs/release-preparation.json').write_text(json.dumps({'greeter_build':{'sha256':recovery.digest(patched)}}))
        wheel=self.cache/'example.whl';wheel.write_bytes(b'wheel-byte-fixture')
        (self.root/'locks/python-wheels.json').write_text(json.dumps([{'filename':wheel.name,'sha256':recovery.digest(wheel),'url':'https://example.invalid/example.whl'}]))
        record={'Filename':'pool/main/e/example/example_1_all.deb','SHA256':recovery.digest(example)}
        with patch.object(recovery,'apt_record',return_value=record):
            self.kit=self.base/'kit'
            recovery.create(self.root,self.kit,[self.cache],write_manifest=True)

    def package(self,name,version):
        tree=self.base/(name+'-'+version);(tree/'DEBIAN').mkdir(parents=True)
        (tree/'DEBIAN/control').write_text(f'Package: {name}\nVersion: {version}\nArchitecture: amd64\nMaintainer: Tests <tests@localhost>\nDescription: Disposable test fixture\n')
        result=self.cache/(name+'_'+version+'_amd64.deb')
        subprocess.run(['dpkg-deb','--root-owner-group','--build',str(tree),str(result)],check=True,stdout=subprocess.DEVNULL)
        return result

    def test_complete_kit_verifies_without_network(self):
        with patch.object(recovery,'apt_record',side_effect=AssertionError('verification must not use APT indexes')):
            self.assertEqual(len(recovery.verify(self.root,self.kit)),4)

    def test_kit_manifest_is_not_its_own_trust_anchor(self):
        manifest=self.kit/'manifest.json';data=json.loads(manifest.read_text());data['artifacts'][0]['sha256']='0'*64
        manifest.write_text(json.dumps(data))
        with self.assertRaises(ValueError):recovery.verify(self.root,self.kit)

    def test_modified_or_missing_archive_rejected(self):
        p=self.kit/'packages/nwg-hello_0.4.2-1+hf1_amd64.deb';p.write_bytes(b'tampered')
        with self.assertRaises(ValueError):recovery.verify(self.root,self.kit)
        p.unlink()
        with self.assertRaises((ValueError,OSError)):recovery.verify(self.root,self.kit)

    def test_artifact_symlink_rejected(self):
        p=self.kit/'packages/nwg-hello_0.4.2-1+hf1_amd64.deb';p.unlink();p.symlink_to(self.original)
        with self.assertRaises(ValueError):recovery.verify(self.root,self.kit)

    def test_stale_manifest_rejected_after_lock_change(self):
        p=self.root/'locks/ubuntu-26.04-amd64.json';p.write_text(p.read_text()+'\n')
        with self.assertRaises(ValueError):recovery.verify(self.root,self.kit)

    def test_existing_destination_is_never_overwritten(self):
        with self.assertRaises(ValueError):recovery.create(self.root,self.kit,[self.cache])

    def test_source_plus_kit_archive_is_reproducible_and_excludes_private_state(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
        for name in ('backups','.cache'):
            folder=self.root/name;folder.mkdir();(folder/'private.txt').write_text('synthetic-private-sentinel')
        (self.kit/'extra-private.txt').write_text('synthetic-private-sentinel')
        first,second=self.base/'one.tar.gz',self.base/'two.tar.gz'
        self.assertEqual(recovery.package(self.root,self.kit,first),recovery.package(self.root,self.kit,second))
        with tarfile.open(first) as archive:
            names=archive.getnames()
            self.assertIn('HyprlandFiles/bundles/ubuntu-26.04-amd64/manifest.json',names)
            self.assertFalse(any('/backups/' in name or '/.cache/' in name or 'extra-private' in name for name in names))


class AutomaticSetup(unittest.TestCase):
    def test_default_profile_follows_hardware(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)
            self.assertEqual(detect_profile(p),'desktop')
            (p/'LID9').mkdir();(p/'LID9/state').write_text('state: closed')
            self.assertEqual(detect_profile(p),'laptop-server')

    def test_unrelated_multiarch_upgrades_are_not_missed(self):
        with self.assertRaises(ValueError):
            reject_unrelated_changes('Inst libshared [1] (2 Ubuntu)',{'libshared:amd64':'1'},{'hyprland'})
        with self.assertRaises(ValueError):
            reject_unrelated_changes('Inst libshared:amd64 [1] (2 Ubuntu)',{'libshared':'1'},{'hyprland'})
        reject_unrelated_changes('Inst hyprland [1] (2 PPA)',{'hyprland:amd64':'1'},{'hyprland'})
        reject_unrelated_changes('Inst new-dependency (1 Ubuntu)',{},set())


if __name__=='__main__':unittest.main()
