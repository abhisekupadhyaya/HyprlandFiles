"""Small, preserving TOML updates for the optional terminal appearance add-on."""
import copy
import json
import re
import tomllib

from hflib import no_symlink_parents, operation

THEME='hyprland-blue-glass'
HEADERS=re.compile(r'(?m)^[ \t]*(\[\[?[^\n]+?\]\]?)[ \t]*(?:#[^\n]*)?(?:\n|$)')


def inline(value):
    if isinstance(value,bool):return str(value).lower()
    if isinstance(value,str):return json.dumps(value,ensure_ascii=False)
    if isinstance(value,dict):return '{ '+', '.join(k+' = '+inline(v) for k,v in value.items())+' }'
    raise ValueError('Unsupported appearance value')


def comment(value):
    """Find an inline comment without mistaking a quoted hex colour for one."""
    quote=None;escaped=False
    for i,char in enumerate(value):
        if escaped:escaped=False;continue
        if quote=='"' and char=='\\':escaped=True;continue
        if quote:
            if char==quote:quote=None
        elif char in ('"',"'"):quote=char
        elif char=='#':
            body=value[:i].rstrip();return body,value[len(body):]
    return value.rstrip(),value[len(value.rstrip()):]


def merge(text,updates):
    """Edit simple root/inline-style values; validate every unrelated TOML value.

    Multiline values or expanded style tables that cannot be edited safely are
    refused before the caller starts its transaction. Comments and arrays that
    are not targeted remain byte-for-byte intact.
    """
    expected=copy.deepcopy(tomllib.loads(text))
    for table,fields in updates.items():
        target=expected.setdefault(table,{}) if table else expected
        if not isinstance(target,dict):raise ValueError('Expected appearance table: '+table)
        for key,update in fields.items():
            old=target.get(key)
            value=dict(old or {},**update) if isinstance(update,dict) else update
            if old==value:continue
            headers=list(HEADERS.finditer(text))
            if not table:start=0;end=headers[0].start() if headers else len(text)
            else:
                found=next((i for i,h in enumerate(headers)
                    if re.fullmatch(r'\[\s*'+re.escape(table)+r'\s*\]',h.group(1))),None)
                if found is None:
                    text+=('' if text.endswith('\n') else '\n')+'\n['+table+']\n'
                    start=end=len(text)
                else:
                    start=headers[found].end()
                    end=headers[found+1].start() if found+1<len(headers) else len(text)
            section=text[start:end]
            pattern=re.compile(r'(?m)^([ \t]*'+re.escape(key)+r'[ \t]*=[ \t]*)([^\n]*)$')
            matches=list(pattern.finditer(section))
            if len(matches)>1:raise ValueError('Ambiguous appearance key: '+key)
            if matches:
                match=matches[0];body,suffix=comment(match.group(2))
                if tomllib.loads('value = '+body).get('value')!=old:
                    raise ValueError('Cannot safely edit appearance key: '+key)
                section=section[:match.start()]+match.group(1)+inline(value)+suffix+section[match.end():]
            else:
                section+=('' if not section or section.endswith('\n') else '\n')+key+' = '+inline(value)+'\n'
            text=text[:start]+section+text[end:];target[key]=value
    if tomllib.loads(text)!=expected:
        raise ValueError('Appearance edit would change unrelated TOML settings')
    return text


def yazi_updates(p):
    # Keep filetype rules, icons, semantic colours and syntax themes inherited.
    # Default/reset backgrounds let the existing terminal glass show through.
    return {
        'mgr':{'cwd':{'fg':p['cyan']},'border_style':{'fg':p['ribbon_blue']}},
        'tabs':{'active':{'fg':p['foreground'],'bg':p['selection'],'bold':True},
                'inactive':{'fg':p['muted'],'bg':'reset'}},
        'mode':{'normal_main':{'fg':p['ink'],'bg':p['accent'],'bold':True},
                'normal_alt':{'fg':p['accent'],'bg':'reset'}},
        'indicator':{'parent':{'bg':p['surface'],'reversed':False},
                     'current':{'bg':p['selection'],'bold':True,'reversed':False}},
        'status':{'overall':{'bg':'reset'}},
    }


def superfile_updates(p):
    # Leave syntax, icons, gradients, copy/error/warning colours and buttons alone.
    return {'':{
        'full_screen_bg':p['background'],'file_panel_bg':p['background'],
        'sidebar_bg':p['background'],'footer_bg':p['background'],'modal_bg':p['background'],
        'file_panel_border':p['ribbon_navy'],'footer_border':p['ribbon_navy'],
        'sidebar_border':p['ribbon_navy'],'sidebar_divider':p['ribbon_navy'],
        'file_panel_border_active':p['accent'],'footer_border_active':p['accent'],
        'sidebar_border_active':p['accent'],'modal_border_active':p['accent'],
        'file_panel_top_path':p['cyan'],'sidebar_title':p['cyan'],
        'file_panel_item_selected_fg':p['foreground'],'file_panel_item_selected_bg':p['selection'],
        'sidebar_item_selected_fg':p['foreground'],'sidebar_item_selected_bg':p['selection'],
    }}


def configuration_operations(root,home,p):
    def read(path,fallback=''):
        no_symlink_parents(path,home)
        if path.is_symlink():raise ValueError('Review the existing file-manager configuration symlink: '+str(path))
        return path.read_text() if path.exists() else fallback
    def changed(path,text):
        no_symlink_parents(path,home)
        if path.is_symlink():raise ValueError('Review the existing file-manager configuration symlink: '+str(path))
        return operation(path,text,path.stat().st_mode&0o777 if path.exists() else 0o644)
    yazi=home/'.config/yazi/theme.toml'
    yazi_text=read(yazi,'# Hyprland Blue Glass: retain Yazi file-type colours, icons and syntax defaults.\n')
    config=home/'.config/superfile/config.toml'
    config_text=read(config,(root/'config/superfile/config.toml').read_text())
    selected=tomllib.loads(config_text).get('theme','catppuccin-mocha')
    if not isinstance(selected,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',selected):
        raise ValueError('Expected a simple Superfile theme name')
    directory=home/'.config/superfile/theme';theme=directory/(THEME+'.toml')
    source=directory/(selected+'.toml')
    theme_text=read(source,(root/'config/superfile/theme/hyprland-blue-glass.toml').read_text())
    # When switching from another theme, keep its rich semantic/syntax palette.
    # Existing copies of that theme and all hotkeys remain untouched.
    return [changed(yazi,merge(yazi_text,yazi_updates(p))),
            changed(theme,merge(theme_text,superfile_updates(p))),
            changed(config,merge(config_text,{'':{'theme':THEME,'transparent_background':True}})),
            operation(home/'.local/share/hyprlandfiles/licenses/superfile.txt',
                      (root/'LICENSES/superfile.txt').read_bytes())]
