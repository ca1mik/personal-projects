"""Local text preference baseline. Only explicit owner ratings are training labels."""
import hashlib,json,math,re,sqlite3
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'artifacts'/'meme-model'

def words(text):return re.findall(r'[а-яёa-z0-9]{2,}',text.lower())

def labeled(feedback):
    unique={}
    for row in feedback:
        if row.get('kind') not in ('meme','memes','video'):continue
        if type(row.get('rating')) is not int or row['rating'] not in (-1,1):continue
        text=str(row.get('example') or '').strip()
        if not words(text):continue
        key=hashlib.sha256(text.casefold().encode()).hexdigest()
        unique[key]={'id':key,'text':text,'label':row['rating'],'source':'explicit_owner_feedback','post':row.get('post')}
    return sorted(unique.values(),key=lambda x:x['id'])

def fit(rows):
    counts={str(c):Counter() for c in (-1,1)};docs=Counter()
    for row in rows:
        key=str(row['label']);docs[key]+=1;counts[key].update(words(row['text']))
    vocab=sorted(set(counts['-1'])|set(counts['1']))
    return {'type':'multinomial_naive_bayes_text','counts':{k:dict(v) for k,v in counts.items()},'documents':dict(docs),'vocabulary_size':len(vocab),'limitations':'Text ranking only; no video, audio or semantic understanding; scores are not calibrated probabilities.'}

def predict(model,text):
    total=sum(model['documents'].values());scores={}
    for c in ('-1','1'):
        counts=model['counts'][c];den=sum(counts.values())+max(1,model['vocabulary_size'])
        scores[c]=math.log(model['documents'][c]/total)+sum(math.log((counts.get(w,0)+1)/den) for w in words(text))
    return 1 if scores['1']>scores['-1'] else -1

def build(feedback):
    rows=labeled(feedback);sizes=Counter(r['label'] for r in rows)
    report={'owner_positive':sizes[1],'owner_negative':sizes[-1],'status':'waiting_for_labels','minimum_per_class':20,'trained':False}
    if min(sizes[1],sizes[-1])<20:return rows,report,None
    train=[];test=[]
    for c in (-1,1):
        group=[r for r in rows if r['label']==c]
        for i,row in enumerate(group):(test if i%5==0 else train).append(row)
    model=fit(train)
    accuracy=sum(predict(model,r['text'])==r['label'] for r in test)/len(test)
    report.update(status='experimental_baseline',trained=True,train_size=len(train),test_size=len(test),holdout_accuracy=accuracy,
                  warning='Small text-only baseline. Held-out accuracy is not evidence of understanding memes.')
    return rows,report,model

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect((ROOT/'data'/'agent.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute("SELECT value FROM kv WHERE key='personal_feedback'").fetchone()
    rows,report,model=build(json.loads(row[0]) if row else [])
    (OUT/'owner-labels.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    observation_path=ROOT/'artifacts'/'meme-observations'/'tiktok-3h-20261024.jsonl'
    observations=[json.loads(s) for s in observation_path.read_text(encoding='utf-8').splitlines() if s.strip()] if observation_path.exists() else []
    report['observation_rows']=len(observations)
    report['observations_are_not_labels']=True
    (OUT/'status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if model:(OUT/'model.json').write_text(json.dumps(model,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
