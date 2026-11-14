"""Small JSONC object editor: preserve comments and unrelated settings verbatim."""
from dataclasses import dataclass, field
import json
import re


def reject_constant(value):raise ValueError('Invalid JSONC constant: '+value)


@dataclass
class Node:
    start: int
    end: int
    value: object
    members: dict = field(default_factory=dict)
    trailing: bool = False


class Parser:
    def __init__(self,text):self.text=text;self.pos=0

    def space(self):
        while self.pos<len(self.text):
            if self.text[self.pos].isspace():self.pos+=1
            elif self.text.startswith('//',self.pos):
                end=self.text.find('\n',self.pos);self.pos=len(self.text) if end<0 else end+1
            elif self.text.startswith('/*',self.pos):
                end=self.text.find('*/',self.pos+2)
                if end<0:raise ValueError('Unterminated JSONC comment')
                self.pos=end+2
            else:break

    def node(self):
        self.space();start=self.pos
        if start>=len(self.text):raise ValueError('Missing JSONC value')
        opening=self.text[start]
        if opening not in '{[':
            try:value,end=json.JSONDecoder(parse_constant=reject_constant).raw_decode(self.text,start)
            except ValueError as exc:raise ValueError('Invalid JSONC value') from exc
            self.pos=end;return Node(start,end,value)
        self.pos+=1;value={} if opening=='{' else [];members={};trailing=False
        closing='}' if opening=='{' else ']'
        self.space()
        if self.text[self.pos:self.pos+1]==closing:
            self.pos+=1;return Node(start,self.pos,value,members)
        while True:
            self.space()
            if opening=='{':
                if self.text[self.pos:self.pos+1]!='"':raise ValueError('Expected JSONC object key')
                key=self.node().value
                if key in members:raise ValueError('Duplicate JSONC key: '+key)
                self.space()
                if self.text[self.pos:self.pos+1]!=':':raise ValueError('Expected JSONC colon')
                self.pos+=1;child=self.node();members[key]=child;value[key]=child.value
            else:value.append(self.node().value)
            self.space();token=self.text[self.pos:self.pos+1]
            if token==closing:self.pos+=1;break
            if token!=',':raise ValueError('Expected JSONC comma or closing bracket')
            self.pos+=1;self.space()
            if self.text[self.pos:self.pos+1]==closing:
                self.pos+=1;trailing=True;break
        return Node(start,self.pos,value,members,trailing)


def parse(text):
    parser=Parser(text);node=parser.node();parser.space()
    if parser.pos!=len(text):raise ValueError('Unexpected trailing JSONC content')
    if not isinstance(node.value,dict):raise ValueError('Settings must be a JSONC object')
    return node


def merge(text,updates):
    text=text if text.strip() else '{}\n';root=parse(text);edits=[]
    def indent(pos):
        line=text[text.rfind('\n',0,pos)+1:pos]
        return re.match(r'[ \t]*',line).group()
    def encoded(value,padding):return json.dumps(value,ensure_ascii=False,indent=2).replace('\n','\n'+padding)
    def visit(node,changes):
        missing={}
        for key,value in changes.items():
            old=node.members.get(key)
            if old is None:missing[key]=value
            elif isinstance(value,dict) and isinstance(old.value,dict):visit(old,value)
            elif old.value!=value:edits.append((old.start,old.end,encoded(value,indent(old.start))))
        if missing:
            padding=indent(node.start);child_padding=padding+'  '
            prefix=''
            if node.members and not node.trailing:
                last=next(reversed(node.members.values()))
                if last.end==node.end-1:prefix=','
                else:edits.append((last.end,last.end,','))
            additions=',\n'.join(child_padding+json.dumps(k)+': '+encoded(v,child_padding) for k,v in missing.items())
            edits.append((node.end-1,node.end-1,prefix+'\n'+additions+'\n'+padding))
    visit(root,updates)
    for start,end,data in sorted(edits,reverse=True):text=text[:start]+data+text[end:]
    parse(text)
    return text
