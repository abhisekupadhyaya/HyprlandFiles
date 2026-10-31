import importlib.machinery,importlib.util,json,os
from pathlib import Path
import subprocess,sys,tempfile,unittest,socket,threading,time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.cache/runtime/lib'))
try:
    from PIL import Image
    import pywal
except ImportError:
    raise unittest.SkipTest('Run python3 tools/prepare_dev.py for extended palette tests')
loader=importlib.machinery.SourceFileLoader('hf_theme',str(ROOT/'bin/hf-theme'))
spec=importlib.util.spec_from_loader(loader.name,loader)
theme=importlib.util.module_from_spec(spec)
loader.exec_module(theme)


class Theme(unittest.TestCase):
    def setUp(self):
        commands=patch.object(theme,'run',return_value=__import__('types').SimpleNamespace(returncode=0,stdout='',stderr=''))
        commands.start();self.addCleanup(commands.stop)
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.state=self.base/'state'
        self.state.mkdir()
        self.patch=patch.object(theme,'STATE',self.state)
        self.patch.start();self.addCleanup(self.patch.stop)

    def image(self,name,shift):
        p=self.base/name
        im=Image.new('RGB',(64,64))
        im.putdata([((x*4+shift)%256,y*4,(x*2+y*2+shift)%256) for y in range(64) for x in range(64)])
        im.save(p)
        return p

    def test_two_wallpapers_change_all_consumers_and_restore_from_cache(self):
        first=theme.generate(self.image('one.png',0))
        theme.select_generation(first)
        second=theme.generate(self.image('two with spaces.png',70))
        theme.select_generation(second)
        self.assertEqual((self.state/'previous').resolve(),first)
        self.assertNotEqual(json.loads((first/'palette.json').read_text())['ui'],json.loads((second/'palette.json').read_text())['ui'])
        palette=json.loads((second/'palette.json').read_text())
        self.assertGreaterEqual(min(palette['contrast'].values()),4.5)
        accent=palette['ui']['accent'][1:]
        for name in ('hyprland.lua','kitty.conf','fuzzel.ini','hyprlock-colors.conf','colors.css','greetd.css'):
            self.assertIn(accent,(second/name).read_text(),name)
        with patch.object(theme,'generate',side_effect=AssertionError('restore must never regenerate')):
            with patch.object(sys,'argv',['hf-theme','restore','--no-apply']):
                theme.main()
        self.assertEqual((self.state/'current').resolve(),second)

    def test_invalid_image_keeps_current_generation(self):
        good=theme.generate(self.image('good.png',10))
        theme.select_generation(good)
        bad=self.base/'broken.png';bad.write_text('not an image')
        with self.assertRaises(OSError):theme.generate(bad)
        self.assertEqual((self.state/'current').resolve(),good)

    def test_cached_generation_does_not_reextract_colours(self):
        source=self.image('cached.png',20)
        good=theme.generate(source)
        from pywal import colors
        with patch.object(colors,'get',side_effect=AssertionError('unexpected palette extraction')):
            self.assertEqual(theme.generate(source),good)

    def test_failed_reload_restores_previous_generation(self):
        a=theme.generate(self.image('first.png',0));theme.select_generation(a)
        b=theme.generate(self.image('second.png',100))
        with patch.object(theme,'generate',return_value=b),patch.object(theme,'apply',side_effect=[RuntimeError('reload failed'),None]):
            with patch.object(sys,'argv',['hf-theme','set','unused.png']):
                with self.assertRaises(RuntimeError):theme.main()
        self.assertEqual((self.state/'current').resolve(),a)

    def test_wallpaper_readiness_wakes_on_socket_creation(self):
        parent=self.base/'hypr/test-instance';parent.mkdir(parents=True)
        server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        def create():
            time.sleep(.05)
            server.bind(str(parent/'.hyprpaper.sock'))
        t=threading.Thread(target=create);t.start()
        try:
            with patch.dict(os.environ,{'XDG_RUNTIME_DIR':str(self.base),'HYPRLAND_INSTANCE_SIGNATURE':'test-instance'}):
                theme.wait_for_wallpaper_socket()
        finally:
            t.join();server.close()


if __name__=='__main__':unittest.main()
