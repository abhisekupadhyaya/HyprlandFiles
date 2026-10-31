import json
from pathlib import Path
import tempfile
import unittest
from hf_runtime import output_scale, internal, gpu_device, lid_state

class Hardware(unittest.TestCase):
    def test_4k_laptop_and_1080p_desktop_scale(self):
        self.assertEqual(output_scale({'name':'eDP-3','modes':[{'current':True,'width':3840}],'physical_size':{'width':340}}),2)
        self.assertEqual(output_scale({'name':'HDMI-A-2','modes':[{'current':True,'width':1920}],'physical_size':{'width':530}}),1)
        self.assertEqual(output_scale({'name':'eDP-1','modes':[{'current':True,'width':3840}]}),2)
        self.assertEqual(output_scale({'name':'DP-2'},'1.5'),1.5)

    def test_different_connector_names(self):
        for name in ('eDP-1','eDP-3','LVDS-2','DSI-1'):self.assertTrue(internal(name))
        for name in ('DP-1','HDMI-A-1','eDP-1";evil'):self.assertFalse(internal(name))

    def test_gpu_selection_without_fixed_card_or_pci(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);sysfs=r/'sys';dev=r/'dev';sysfs.mkdir();dev.mkdir()
            for name,pci,vendor,driver in [('card7','0000:04:00.0','0x8086','i915'),('card0','0000:09:00.0','0x10de','nouveau')]:
                device=r/pci;device.mkdir();(device/'vendor').write_text(vendor)
                (device/'driver').symlink_to(r/driver)
                card=sysfs/name;card.mkdir();(card/'device').symlink_to(device)
                (dev/name).touch()
            self.assertEqual(gpu_device('auto',sysfs,dev),str(dev/'card7'))
            self.assertEqual(gpu_device('0000:09:00.0',sysfs,dev),str(dev/'card0'))
            self.assertIsNone(gpu_device('default',sysfs,dev))
            with self.assertRaises(ValueError):gpu_device('0000:ff:00.0',sysfs,dev)

    def test_lid_absent_and_multiple_states(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);self.assertEqual(lid_state(r),'unknown')
            (r/'A').mkdir();(r/'A/state').write_text('state: open')
            self.assertEqual(lid_state(r),'open')
            (r/'B').mkdir();(r/'B/state').write_text('state: closed')
            self.assertEqual(lid_state(r),'closed')

if __name__=='__main__':unittest.main()
