import json
from pathlib import Path
import unittest
import sbom

ROOT=Path(__file__).resolve().parents[1]

class Inventory(unittest.TestCase):
    def test_recovery_hashes_are_exactly_represented(self):
        manifest=json.loads((ROOT/sbom.MANIFEST).read_text())
        data=sbom.generate(ROOT)
        self.assertEqual(len(data['packages']),len(manifest['artifacts']))
        self.assertEqual({p['checksums'][0]['checksumValue'] for p in data['packages']},{x['sha256'] for x in manifest['artifacts']})
        self.assertEqual(len({p['SPDXID'] for p in data['packages']}),len(data['packages']))
        self.assertTrue(all(not x['filesAnalyzed'] for x in data['packages']))
        self.assertEqual(data['spdxVersion'],'SPDX-2.3')

    def test_inventory_is_deterministic_and_not_an_os_support_claim(self):
        self.assertEqual(sbom.generate(ROOT),sbom.generate(ROOT))
        self.assertIn('Excludes',sbom.generate(ROOT)['comment'])
