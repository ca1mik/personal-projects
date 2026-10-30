"""Offline Russian SAPI speech into Ogg/Opus. Never speaks through the PC speakers."""
import json,sys
from pathlib import Path

def synthesize(text,output):
    import win32com.client,av
    output=Path(output);wav=output.with_suffix('.wav')
    voice=win32com.client.Dispatch('SAPI.SpVoice')
    russian=[v for v in voice.GetVoices() if '419' in v.GetAttribute('Language').split(';')]
    if not russian:raise RuntimeError('Russian Windows speech voice is not installed')
    voice.Voice=russian[0]
    stream=win32com.client.Dispatch('SAPI.SpFileStream')
    stream.Open(str(wav),3,False)
    try:voice.AudioOutputStream=stream;voice.Speak(text[:1400])
    finally:stream.Close()
    try:
        with av.open(str(wav)) as source,av.open(str(output),'w',format='ogg') as target:
            out=target.add_stream('libopus',rate=48000);out.layout='mono'
            resampler=av.AudioResampler(format='flt',layout='mono',rate=48000)
            for frame in source.decode(audio=0):
                for converted in resampler.resample(frame):
                    for packet in out.encode(converted):target.mux(packet)
            for converted in resampler.resample(None):
                for packet in out.encode(converted):target.mux(packet)
            for packet in out.encode(None):target.mux(packet)
    finally:wav.unlink(missing_ok=True)
    return output

if __name__=='__main__':
    data=json.load(sys.stdin);print(synthesize(data['text'],data['output']))
