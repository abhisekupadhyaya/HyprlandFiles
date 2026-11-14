#!/usr/bin/python3
"""Opt-in user-level Bash, Ghostty and VS Code styling with exact inputs/backups."""
import argparse
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import platform
import subprocess
import sys
import tarfile

from hflib import Transaction, checked_download, managed_state, operation, no_symlink_parents
from jsonc import merge as merge_jsonc

ROOT=Path(__file__).resolve().parents[1]
BEGIN='# >>> HyprlandFiles shared Bash style >>>'
END='# <<< HyprlandFiles shared Bash style <<<'
FONTS=('Regular','Bold','Italic','BoldItalic')


def managed_block(text,body,begin=BEGIN,end=END):
    block=begin+'\n'+body.rstrip()+'\n'+end+'\n'
    if begin in text or end in text:
        if text.count(begin)!=1 or text.count(end)!=1 or text.index(end)<text.index(begin):
            raise ValueError('Malformed managed configuration block; preserve and merge it manually')
        start=text.index(begin);stop=text.index(end)+len(end)
        if text[stop:stop+1]=='\n':stop+=1
        return text[:start]+block+text[stop:]
    return text+('' if not text or text.endswith('\n') else '\n')+'\n'+block


def prompt(p):
    def segment(kind,template,color,background='transparent',options=None,min_width=0):
        result=dict(type=kind,style='plain' if background=='transparent' else 'diamond',
                    foreground=color,background=background,
                    leading_diamond='',trailing_diamond='\ue0b0',template=template)
        if options:result['options']=options
        if min_width:result['min_width']=min_width
        return result
    # Environment labels use exported activation markers only. Never start a
    # Python/Conda/pyenv interpreter or read .env files to draw the prompt.
    environment=(
        '{{- $name := "" -}}{{- $prefix := "" -}}{{- $icon := "\ue73c" -}}'
        '{{- if .Env.VIRTUAL_ENV -}}'
        '{{- $name = base (clean .Env.VIRTUAL_ENV) -}}'
        '{{- if and .Env.VIRTUAL_ENV_PROMPT (not (has .Env.VIRTUAL_ENV_PROMPT (list ".venv" "venv" "env"))) -}}'
        '{{- $name = trimAll "() " .Env.VIRTUAL_ENV_PROMPT -}}'
        '{{- else if has $name (list ".venv" "venv" "env") -}}'
        '{{- $name = base (dir (clean .Env.VIRTUAL_ENV)) -}}{{- end -}}'
        '{{- else if or .Env.CONDA_DEFAULT_ENV .Env.CONDA_PREFIX -}}'
        '{{- $prefix = "conda:" -}}{{- $name = base (coalesce .Env.CONDA_DEFAULT_ENV .Env.CONDA_PREFIX) -}}'
        '{{- else if and .Env.PYENV_VERSION (ne .Env.PYENV_VERSION "system") -}}'
        '{{- $name = .Env.PYENV_VERSION -}}'
        '{{- else if .Env.DIRENV_DIR -}}'
        '{{- $icon = "env" -}}{{- $name = base (trimPrefix "-" .Env.DIRENV_DIR) -}}'
        '{{- end -}}'
        '{{- if $name -}}{{- if gt (len $name) 18 -}}'
        '{{- $name = printf "%s…%s" (trunc 8 $name) (trunc -8 $name) -}}{{- end }}'
        ' {{ $icon }} {{ $prefix }}{{ $name }} {{ end }}')
    location=(
        ' {{ if eq .Path "~" }}\uf015 ~'
        '{{ else }}\uf07b '
        '{{ if and .Segments.Git (ne .Segments.Git.RepoName .Path) }}'
        '{{ abbrev 15 .Segments.Git.RepoName }}/{{ abbrev 14 .Path }}'
        '{{ else }}{{ abbrev 24 .Path }}{{ end }}{{ end }} ')
    branch=(
        ' \ue0a0 {{ if .Detached }}{{ .HEAD }}{{ else }}'
        '{{ $branch := .Ref }}{{ if gt (len $branch) 22 }}'
        '{{ if contains "/" $branch }}{{ trunc 6 (first (splitList "/" $branch)) }}/…{{ trunc -12 $branch }}'
        '{{ else }}{{ abbrev 22 $branch }}{{ end }}'
        '{{ else }}{{ $branch }}{{ end }}{{ end }}'
        '{{ if .Working.Changed }} <'+p['ansi'][3]+'>*</>{{ end }}'
        '{{ if .Staging.Changed }} +{{ end }} ')
    location_segment=segment('path',location,p['foreground'],p['ribbon_navy'],dict(style='folder',home_icon='~'))
    location_segment['leading_diamond']='\ue0b6'
    indicator=segment('status','\u276f',p['accent'],options=dict(always_enabled=True))
    indicator['foreground_templates']=['{{ if ne .Code 0 }}'+p['ansi'][1]+'{{ end }}']
    return {'$schema':'https://raw.githubusercontent.com/JanDeDobbeleer/oh-my-posh/v32.0.0/themes/schema.json',
        'version':4,'final_space':True,'terminal_background':p['background'],
        'shell_integration':False,'enable_cursor_positioning':False,
        'blocks':[
            dict(type='prompt',alignment='left',newline=False,segments=[
                segment('text','\n\u256d\u2500 ',p['accent']),
                segment('session','\uf489 {{ .UserName }}@{{ .HostName }}  ',p['muted']),
                location_segment,
                segment('git',branch,p['accent'],p['surface'],dict(branch_icon='',commit_icon='commit:',tag_icon='tag:'),min_width=110),
                segment('text',environment,p['ink'],p['ribbon_cyan']),
                # The Node badge is project-scoped. NVM already exports the
                # selected version in its activation path: no node/npm process
                # or version-cache invalidation is required to display it.
                segment('node',' \ue719 {{ if .Env.NVM_BIN }}{{ $version := base (dir (clean .Env.NVM_BIN)) }}'
                    '{{ if regexMatch "^v[0-9]+[.][0-9]+[.][0-9]+$" $version }}{{ trimPrefix "v" $version }}'
                    '{{ else }}node{{ end }}{{ else }}node{{ end }} ',p['cyan'],p['ribbon_navy'],
                    dict(display_mode='files',extensions=['package.json','.nvmrc','.node-version','pnpm-workspace.yaml'],
                         project_files=['package.json','pnpm-workspace.yaml'],
                         fetch_package_manager=False,cache_duration='none'),min_width=75),
                segment('executiontime','  {{ .FormattedMs }}',p['muted'],options=dict(threshold=2000,style='austin')),
                segment('status','  exit {{ .Code }}',p['ansi'][1])]),
            dict(type='prompt',alignment='left',newline=True,segments=[
                segment('text','\u2570\u2500 ',p['accent']),indicator])
        ]}


def ghostty(p):
    options={'command':'/bin/bash','font-family':p['font'],'font-size':'11','window-theme':'ghostty',
        'window-padding-x':'14','window-padding-y':'14','background-opacity':str(p['glass']['opacity']),
        'background-blur':'64','background-opacity-cells':'false',
        'background':p['background'],'foreground':p['foreground'],'cursor-color':p['accent'],
        'selection-background':p['selection'],'selection-foreground':p['foreground'],
        'copy-on-select':'true'}
    return ('# Hyprland Blue Glass: black tint, frosted background, opaque prompt ribbons.\n'+
        'font-family = ""\n'+
        ''.join(f'{k} = {v}\n' for k,v in options.items())+
        ''.join(f'palette = {i}={c}\n' for i,c in enumerate(p['ansi'])))


def code_settings(p):
    colors={key:p['background'] for key in (
        'editor.background','terminal.background','panel.background','sideBar.background',
        'activityBar.background','statusBar.background','statusBar.noFolderBackground',
        'titleBar.activeBackground','titleBar.inactiveBackground','tab.activeBackground',
        'editorGroupHeader.tabsBackground')}
    colors.update({key:p['foreground'] for key in ('editor.foreground','terminal.foreground','foreground')})
    colors.update({'terminalCursor.foreground':p['accent'],'terminal.selectionBackground':p['selection'],
        'editor.selectionBackground':p['selection'],'editor.lineHighlightBackground':p['surface'],
        'editorCursor.foreground':p['accent'],'editorLineNumber.foreground':p['muted'],
        'editorLineNumber.activeForeground':p['accent'],'focusBorder':p['accent'],
        'panel.border':p['border'],'sideBar.border':p['border'],'tab.activeBorderTop':p['accent'],
        'tab.inactiveBackground':p['surface'],'statusBar.foreground':p['accent'],
        'statusBarItem.remoteBackground':'#0B2447','statusBarItem.remoteForeground':p['cyan'],
        'activityBar.activeBorder':p['accent'],
        'button.background':'#1D4ED8','button.foreground':'#EFF6FF','button.hoverBackground':'#2563EB',
        'textLink.foreground':p['cyan']})
    names=('Black','Red','Green','Yellow','Blue','Magenta','Cyan','White')
    colors.update({'terminal.ansi'+('Bright' if i>=8 else '')+names[i%8]:c for i,c in enumerate(p['ansi'])})
    return {'terminal.integrated.profiles.linux':{'Bash (HyprlandFiles)':{'path':'/bin/bash','args':[]}},
        'terminal.integrated.defaultProfile.linux':'Bash (HyprlandFiles)',
        'terminal.integrated.fontFamily':"'"+p['font']+"', 'JetBrains Mono', 'SFMono-Regular', Consolas, monospace",
        'terminal.integrated.fontSize':14,'terminal.integrated.lineHeight':1.1,
        'terminal.integrated.cursorStyle':'line','terminal.integrated.cursorBlinking':False,
        'terminal.integrated.shellIntegration.enabled':True,
        'window.autoDetectColorScheme':False,'workbench.colorTheme':'Dark Modern',
        'workbench.preferredDarkColorTheme':'Dark Modern','workbench.preferredLightColorTheme':'Dark Modern',
        'workbench.colorCustomizations':colors}


def code_glass_settings(p):
    # Application-scoped: Remote SSH Machine settings cannot apply these to the
    # client. Include them in local desktop preferences and the client export.
    return {'workbench.experimental.modernUI':True,'workbench.modernUIFrostedGlass':True,
            'workbench.modernUIFrostedGlassOpacity':p['glass']['vscode_opacity']}


def hypr_glass(p):
    g=p['glass']
    return ('-- Shared terminal style: dark frosted glass; no opacity rule dims text.\n'
        'hl.config({ decoration = { blur = { enabled = true, '
        f'size = {g["blur_size"]}, passes = {g["blur_passes"]}, noise = {g["noise"]}, '
        f'vibrancy = {g["vibrancy"]}, new_optimizations = true'
        ' } } })\n')


def safe_members(archive):
    members=archive.getmembers()
    if sum(m.size for m in members)>512_000_000:raise ValueError('Terminal archive too large')
    for m in members:
        path=PurePosixPath(m.name)
        if path.is_absolute() or '..' in path.parts or not (m.isdir() or m.isfile()):
            raise ValueError('Unsafe terminal archive member: '+m.name)
    return members


def assets(root,cache):
    paths={}
    for item in json.loads((root/'locks/terminal-amd64.json').read_text()):
        paths[item['name']]=checked_download(item['url'],item['sha256'],cache/item['filename'])
    return paths


def payload_operations(home,inputs):
    ops=[operation(home/'.local/bin/oh-my-posh',inputs['Oh My Posh'].read_bytes(),0o755)]
    with tarfile.open(inputs['JetBrains Mono Nerd Font']) as archive:
        safe_members(archive)
        for style in FONTS:
            name='JetBrainsMonoNerdFontMono-'+style+'.ttf'
            ops.append(operation(home/'.local/share/fonts/hyprlandfiles'/name,archive.extractfile(name).read()))
        ops.append(operation(home/'.local/share/fonts/hyprlandfiles/OFL.txt',archive.extractfile('OFL.txt').read()))
    with tarfile.open(inputs['ble.sh']) as archive:
        for member in safe_members(archive):
            if not member.isfile():continue
            relative=PurePosixPath(member.name).relative_to('ble-0.4.0-devel3')
            ops.append(operation(home/'.local/share/hyprlandfiles/ble'/relative,
                                 archive.extractfile(member).read()))
    return ops


def configuration_operations(root,home,preserve_typography=False):
    p=json.loads((root/'config/terminal/blue-oled.json').read_text())
    directory=home/'.config/hyprlandfiles/terminal'
    settings=code_settings(p)
    if preserve_typography:
        for key in ('terminal.integrated.fontFamily','terminal.integrated.fontSize','terminal.integrated.lineHeight'):
            settings.pop(key,None)
    local_settings=dict(settings,**code_glass_settings(p))
    ghostty_text=ghostty(p)
    if preserve_typography:
        old=directory/'ghostty.conf';no_symlink_parents(old,home)
        if old.is_symlink():raise ValueError('Review the existing terminal style symlink before setup')
        is_typography=lambda line:line.partition('=')[0].strip().startswith(('font-','adjust-'))
        preserved=[line for line in old.read_text().splitlines() if is_typography(line)] if old.is_file() else []
        ghostty_text='\n'.join([*preserved,*[line for line in ghostty_text.splitlines() if not is_typography(line)]])+'\n'
    ops=[operation(directory/'blue-oled.omp.json',json.dumps(prompt(p),indent=2)+'\n'),
         operation(directory/'ghostty.conf',ghostty_text),
         operation(directory/'vscode-settings.json',json.dumps(local_settings,indent=2)+'\n'),
         operation(directory/'vscode-glass.settings.json',json.dumps(code_glass_settings(p),indent=2)+'\n'),
         operation(directory/'hypr-glass.lua',hypr_glass(p)),
         operation(directory/'terminal.bash',(root/'config/bash/terminal.bash').read_bytes())]
    appearance=home/'.config/hypr/appearance.lua'
    if appearance.is_file():
        no_symlink_parents(appearance,home)
        if appearance.is_symlink():raise ValueError('Review the existing Hyprland appearance symlink before setup')
        text=appearance.read_text()
        if '/.config/hyprlandfiles/terminal/hypr-glass.lua' not in text:
            body=('local hf_glass = os.getenv("HOME") .. "/.config/hyprlandfiles/terminal/hypr-glass.lua"\n'
                  'local hf_glass_file = io.open(hf_glass, "r")\n'
                  'if hf_glass_file then hf_glass_file:close(); dofile(hf_glass) end')
            text=managed_block(text,body,'-- >>> HyprlandFiles terminal glass >>>','-- <<< HyprlandFiles terminal glass <<<')
        ops.append(operation(appearance,text,appearance.stat().st_mode&0o777))
    bashrc=home/'.bashrc'
    no_symlink_parents(bashrc,home)
    if bashrc.is_symlink():raise ValueError('Review the existing Bash configuration symlink before setup')
    body='if [[ -r "$HOME/.config/hyprlandfiles/terminal/terminal.bash" ]]; then\n    source "$HOME/.config/hyprlandfiles/terminal/terminal.bash"\nfi'
    ops.append(operation(bashrc,managed_block(bashrc.read_text() if bashrc.exists() else '',body),
                         bashrc.stat().st_mode&0o777 if bashrc.exists() else 0o644))
    target=home/'.config/ghostty/config.ghostty'
    no_symlink_parents(target,home)
    if target.is_symlink():raise ValueError('Review the existing Ghostty configuration symlink before setup')
    text=target.read_text() if target.exists() else (root/'config/ghostty/config.ghostty').read_text().replace('@HOME@',str(home))
    include='config-file = ?'+str(directory/'ghostty.conf')
    if include not in text:
        text=managed_block(text,include,'# >>> HyprlandFiles terminal colours >>>','# <<< HyprlandFiles terminal colours <<<')
    ops.append(operation(target,text,target.stat().st_mode&0o777 if target.exists() else 0o644))
    # Set local desktop preferences and this host's Remote SSH window settings.
    targets=[home/'.config/Code/User/settings.json']
    if (home/'.vscode-server').is_dir():targets.append(home/'.vscode-server/data/Machine/settings.json')
    for target in targets:
        no_symlink_parents(target,home)
        if target.is_symlink():raise ValueError('Review the existing VS Code settings symlink before setup')
        original=target.read_text() if target.exists() else '{}\n'
        updates=settings if '.vscode-server' in target.parts else local_settings
        ops.append(operation(target,merge_jsonc(original,updates),target.stat().st_mode&0o777 if target.exists() else 0o644))
    ops.append(operation(home/'.local/share/hyprlandfiles/licenses/oh-my-posh.txt',
                         (root/'LICENSES/oh-my-posh.txt').read_bytes()))
    return ops


def apply(root,home,cache,style_only=False):
    if os.geteuid()==0:raise ValueError('Run terminal setup as the desktop user, without sudo')
    if platform.machine() not in ('x86_64','amd64') or sys.platform!='linux':
        raise ValueError('The retained prompt executable supports Linux amd64')
    store=home/'.local/state/hyprlandfiles/backups'
    store.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (store.parent/'installer.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # Parse existing settings and verify all targets before downloading.
        config=configuration_operations(root,home,preserve_typography=style_only)
        tx=Transaction(store,home,managed_state(store))
        tx.apply(config,adopt=True,dry_run=True)
        ops=config if style_only else payload_operations(home,assets(root,cache))+config
        backup=tx.apply(ops,adopt=True)
    if not style_only:subprocess.run(['fc-cache','-f',str(home/'.local/share/fonts/hyprlandfiles')],check=True)
    subprocess.run(['/bin/bash','-n',str(home/'.bashrc')],check=True)
    subprocess.run(['/bin/bash','-n',str(home/'.config/hyprlandfiles/terminal/terminal.bash')],check=True)
    subprocess.run(['ghostty','+validate-config','--config-file='+str(home/'.config/ghostty/config.ghostty')],check=True)
    print('Shared Bash ribbon prompt and black/blue frosted-glass styling installed.')
    print('Open a new Ghostty or VS Code terminal. Current sessions and workloads were preserved.')
    if (home/'.vscode-server').is_dir():
        print('Remote SSH prompt/colours are configured. VS Code glass controls are client application settings; see the exported vscode-glass.settings.json.')
    return backup


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('apply','prepare'))
    parser.add_argument('--cache',type=Path,default=ROOT/'.cache/terminal/inputs')
    parser.add_argument('--style-only',action='store_true',help='Update styling without downloading or replacing fonts/tools')
    args=parser.parse_args()
    try:
        if args.action=='prepare':assets(ROOT,args.cache);print('Verified all three terminal inputs; no user settings changed.')
        else:apply(ROOT,Path.home(),args.cache,args.style_only)
    except (OSError,ValueError,subprocess.SubprocessError) as exc:sys.exit(str(exc))
