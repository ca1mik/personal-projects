"""Explicit editorial packets; ordinary replies never become delayed posts."""
import re

MARKER = re.compile(r'^<!-- feed-post:(news|memes|ideas|facts|mail) -->\s*$', re.M)
TAGS = {'news':'#Новости', 'memes':'#Мемы', 'ideas':'#Идеи', 'facts':'#Интересное', 'mail':'#Почта'}

def packets(text):
    matches=list(MARKER.finditer(text))
    if not matches:return []
    result=[]
    for i,m in enumerate(matches):
        body=text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip()
        if not body:continue
        kind=m.group(1)
        if TAGS[kind] not in body:body+='\n\n'+TAGS[kind]
        result.append((kind,body))
    return result[:4]

def without_local_images(text):
    return re.sub(r'!\[[^\]]*\]\(<?[A-Za-z]:[\\/][^)>]+>?\)', '', text).strip()

def plain_caption(text):
    text=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',r'\1 (\2)',text)
    text=re.sub(r'^#{1,3}\s+','',text,flags=re.M)
    return text.replace('**','').replace('`','').strip()
