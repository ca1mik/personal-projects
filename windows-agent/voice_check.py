"""Local speech recognition acceptance check using Windows SAPI (no desktop input)."""
import asyncio,json
from pathlib import Path
import win32com.client
from localagent.base import ROOT,Store,write_json
from localagent.tools import Tools

async def main():
    voice=win32com.client.Dispatch('SAPI.SpVoice')
    selected=None
    for token in voice.GetVoices():
        if 'Russian' in token.GetDescription() or 'Irina' in token.GetDescription():
            voice.Voice=token;selected=token.GetDescription();break
    path=ROOT.parents[1]/'work'/'voice-check.wav'
    stream=win32com.client.Dispatch('SAPI.SpFileStream')
    stream.Open(str(path),3,False)
    voice.AudioOutputStream=stream
    expected='Привет. Создай новый проект и отправь мне готовый архив.'
    voice.Speak(expected);stream.Close()
    transcript=await Tools(Store(),None,None).transcribe(path)
    report={'voice':selected,'expected':expected,'transcript':transcript,
            'passed':all(word in transcript.lower() for word in ('проект','архив'))}
    write_json(ROOT/'artifacts'/'voice-check.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':asyncio.run(main())
