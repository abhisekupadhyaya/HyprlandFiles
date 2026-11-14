"""Native prompt checks use only a verified, optionally retained executable."""
import hashlib
import json
import os
import getpass
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import terminal_setup

ROOT=Path(__file__).resolve().parents[1]


class NativeContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=ROOT/'.cache/terminal/inputs/posh-linux-amd64'
        if not source.is_file() or not shutil.which('git'):
            raise unittest.SkipTest('Prepare the optional terminal add-on inputs for native prompt tests')
        lock=next(x for x in json.loads((ROOT/'locks/terminal-amd64.json').read_text()) if x['name']=='Oh My Posh')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=lock['sha256']:
            raise ValueError('Retained prompt executable differs from its lock')
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.base=Path(cls.temp.name);cls.binary=cls.base/'oh-my-posh'
        shutil.copyfile(source,cls.binary);cls.binary.chmod(0o755)
        cls.config=cls.base/'prompt.json'
        palette=json.loads((ROOT/'config/terminal/blue-oled.json').read_text())
        cls.config.write_text(json.dumps(terminal_setup.prompt(palette)))

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=self.base);self.addCleanup(self.tmp.cleanup)
        self.directory=Path(self.tmp.name);self.repo=self.directory/'workspace';self.repo.mkdir()
        (self.directory/'home').mkdir();(self.directory/'cache').mkdir()
        self.env=dict(os.environ,HOME=str(self.directory/'home'),XDG_CACHE_HOME=str(self.directory/'cache'),
                      SSH_CONNECTION='127.0.0.1 12345 127.0.0.1 22')
        for name in ('VIRTUAL_ENV','VIRTUAL_ENV_PROMPT','CONDA_DEFAULT_ENV','CONDA_PREFIX','PYENV_VERSION','DIRENV_DIR','NVM_BIN','HF_PROMPT_GAP_EXTERNAL'):
            self.env.pop(name,None)
        self.git('init','-q','-b','main')
        (self.repo/'tracked').write_text('fixture\n');self.git('add','tracked');self.git('commit','-q','-m','fixture')

    def git(self,*args):
        subprocess.run(['git','-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false',
            '-c','user.name=Test','-c','user.email=test@example.invalid',*args],
            cwd=self.repo,env=self.env,check=True,capture_output=True,text=True)

    def render(self,context=None,width=120,elapsed=33,status=0,cwd=None):
        result=subprocess.run([str(self.binary),'print','primary','--config',str(self.config),'--shell','bash',
            '--terminal-width',str(width),'--execution-time',str(elapsed),'--status',str(status)],
            env=dict(self.env,**(context or {})),cwd=cwd or self.repo,check=True,capture_output=True,text=True)
        raw=result.stdout.replace('\\[','').replace('\\]','')
        self.assertNotIn('TEMPLATE ERROR',raw);self.assertNotIn('CONFIG ERROR',raw)
        return re.sub(r'\x1b\[[0-9;]*m','',raw),raw

    def test_environment_switches_are_live_and_do_not_execute_python(self):
        binary_dir=self.directory/'bin';binary_dir.mkdir();marker=self.directory/'python-ran'
        for name in ('python','python3','conda','pyenv'):
            script=binary_dir/name;script.write_text('#!/bin/sh\nprintf x >> "'+str(marker)+'"\nexit 1\n');script.chmod(0o755)
        common={'PATH':str(binary_dir)+':'+self.env['PATH']}
        cases=[({},None),({'VIRTUAL_ENV':'/work/vision/.venv','VIRTUAL_ENV_PROMPT':'.venv'},'vision'),
            ({'VIRTUAL_ENV':'/work/service/venv'},'service'),
            ({'VIRTUAL_ENV':'/work/vision/.venv','VIRTUAL_ENV_PROMPT':'prod-analysis'},'prod-analysis'),
            ({'CONDA_DEFAULT_ENV':'analytics'},'conda:analytics'),
            ({'CONDA_PREFIX':'/opt/conda/envs/research'},'conda:research'),
            ({'PYENV_VERSION':'3.13.2'},'3.13.2'),({'DIRENV_DIR':'-/work/api'},'env api')]
        for context,label in cases:
            with self.subTest(context=context):
                text,_=self.render(dict(common,**context))
                if label:self.assertIn(label,text)
                else:self.assertNotIn('\ue73c',text)
        nested,_=self.render(dict(common,VIRTUAL_ENV='/work/service/.venv',CONDA_DEFAULT_ENV='base'))
        self.assertIn('service',nested);self.assertNotIn('conda:base',nested)
        self.assertFalse(marker.exists(),'Environment labels must not run interpreters or managers')

    def test_node_context_tracks_nvm_without_probing_interpreters(self):
        logs=[];paths=[]
        for name,version in [('node-a','22.12.3'),('node-b','24.1.2')]:
            directory=self.directory/name/('v'+version)/'bin';directory.mkdir(parents=True);log=directory/'calls';logs.append(log)
            script=directory/'node';script.write_text('#!/bin/sh\nprintf x >> "'+str(log)+'"\nprintf "v'+version+'\\n"\n');script.chmod(0o755)
            paths.append(directory)
        context=lambda i:dict(PATH=str(paths[i])+':'+self.env['PATH'],NVM_BIN=str(paths[i]))
        text,_=self.render(context(0));self.assertNotIn('22.12.3',text);self.assertFalse(logs[0].exists())
        (self.repo/'package.json').write_text('{"name":"fixture"}')
        nested=self.repo/'src';nested.mkdir()
        for _ in range(3):
            text,_=self.render(context(0),cwd=nested);self.assertIn('22.12.3',text)
        text,_=self.render(context(1),cwd=nested)
        self.assertIn('24.1.2',text);self.assertNotIn('22.12.3',text)
        self.assertFalse(any(log.exists() for log in logs),'Node badges must not execute an interpreter')

    def test_compact_input_and_conditional_feedback(self):
        for width in (40,80,120):
            text,_=self.render({'VIRTUAL_ENV':'/work/vision/.venv'},width=width)
            self.assertTrue(text.startswith('\n\uf489 '),repr(text))
            self.assertEqual(text.splitlines()[-1],'\u276f ')
            self.assertIn(getpass.getuser()+'@',text)
            self.assertIn('vision',text)
            for noise in ('RAM:','UTC','33ms','0ms'):
                self.assertNotIn(noise,text)
        text,_=self.render({'HF_PROMPT_GAP_EXTERNAL':'1'})
        self.assertTrue(text.startswith('\uf489 '),repr(text))
        self.assertNotIn('\n\n',text)
        text,_=self.render(elapsed=2500);self.assertIn('2.5s',text)
        text,raw=self.render(status=7)
        self.assertIn('exit 7',text)
        self.assertIn('\x1b[38;2;255;123;134m\u276f',raw)

    def test_paths_and_long_branches_keep_context_without_stale_git_cache(self):
        nested=self.repo/'tests';nested.mkdir()
        text,_=self.render(cwd=nested);self.assertIn('workspace/tests',text)
        branch='feat/a-very-long-topic-with-production-fix'
        self.git('checkout','-q','-b',branch)
        text,_=self.render(cwd=nested)
        self.assertIn('feat/…',text);self.assertIn('oduction-fix',text);self.assertNotIn(branch,text)
        self.git('checkout','-q','main')
        text,_=self.render();self.assertIn('main',text);self.assertNotIn('feat/…',text)


if __name__=='__main__':unittest.main()
