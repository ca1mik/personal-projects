"""Real local integration checks. Does not send anything to Telegram unless explicitly requested."""
import asyncio,json,sys,time
from localagent.base import ROOT,Store,write_json
from localagent.codex import Codex,SCHEMA
from localagent.tools import Tools

async def main():
    codex=Codex();store=Store();tools=Tools(store,codex,None)
    output={}
    output['codex_schema']=await codex.run('smoke-plan','Return a finish action with summary smoke and arguments containing text CODEX_SCHEMA_OK. No tools.',ROOT/'projects'/'smoke-plan',schema=SCHEMA,timeout=180)
    output['gui']='Not tested further: user stopped Computer Use with Escape.'
    output['development']=await tools.develop('smoke-project',{'spec':'Create a small standard-library-only Python project with a function monthly_payment(principal,annual_rate,months) computing amortized loan payment, including zero-interest handling, rejecting negative principal, rate and nonpositive months. Build a CLI, README and meaningful unittest tests. Actually run python -m unittest discover -v and record output in VALIDATION.md. Use no external services. No subagents.'})
    write_json(ROOT/'artifacts'/'smoke-result.json',output)
    print(json.dumps(output,ensure_ascii=False,indent=2))

if __name__=='__main__': asyncio.run(main())
