"""Check the Ogg/Opus codec used by Telegram voice messages, without sending user audio anywhere."""
import asyncio,json
import av
from localagent.base import ROOT,Store,write_json
from localagent.tools import Tools

async def main():
    work=ROOT.parents[1]/'work'
    source=work/'voice-check.wav'
    target=work/'voice-check.ogg'
    with av.open(str(source)) as incoming, av.open(str(target),'w',format='ogg') as outgoing:
        stream=outgoing.add_stream('libopus',rate=48000)
        stream.layout='mono'
        resampler=av.AudioResampler(format='flt',layout='mono',rate=48000)
        for frame in incoming.decode(audio=0):
            for converted in resampler.resample(frame):
                for packet in stream.encode(converted):outgoing.mux(packet)
        for converted in resampler.resample(None):
            for packet in stream.encode(converted):outgoing.mux(packet)
        for packet in stream.encode(None):outgoing.mux(packet)
    text=await Tools(Store(),None,None).transcribe(target,'opus-check')
    result={'format':'Ogg/Opus, mono, 48000 Hz','transcript':text,'passed':all(w in text.lower() for w in ('проект','архив'))}
    write_json(ROOT/'artifacts'/'opus-check.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':asyncio.run(main())
