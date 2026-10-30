from meme_model import build,labeled,predict

def test_observer_status_is_never_an_owner_label():
    assert labeled([{'kind':'meme','status':'candidate','owner_rating':None,'example':'мем'}])==[]
    assert labeled([{'kind':'news','rating':1,'example':'новость'}])==[]

def test_repeated_text_does_not_inflate_label_count():
    rows=[{'kind':'meme','rating':1,'example':'Один мем'}]*50
    labels,report,model=build(rows)
    assert len(labels)==1 and not report['trained'] and model is None

def test_baseline_has_disjoint_holdout_and_both_classes():
    feedback=[{'kind':'meme','rating':c,'example':('кот абсурд ' if c==1 else 'магазин реклама ')+str(i)} for c in (-1,1) for i in range(20)]
    rows,report,model=build(feedback)
    assert report['train_size']==32 and report['test_size']==8
    assert predict(model,'кот абсурд')==1 and predict(model,'магазин реклама')==-1
