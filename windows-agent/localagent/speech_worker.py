"""Separate process so /stop can terminate recognition immediately."""
import json,os,sys
from pathlib import Path

def main():
    os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING']='1'
    from faster_whisper import WhisperModel
    root=Path(__file__).resolve().parents[1]
    model=WhisperModel('base',device='cpu',compute_type='int8',cpu_threads=2,download_root=str(root/'models'))
    segments,info=model.transcribe(sys.argv[1],language='ru',vad_filter=True,beam_size=5)
    text=' '.join(s.text for s in segments if not(s.no_speech_prob>.6 and s.avg_logprob < -1)).strip()
    Path(sys.argv[2]).write_text(json.dumps({'text':text},ensure_ascii=False),'utf-8')

if __name__=='__main__':main()
