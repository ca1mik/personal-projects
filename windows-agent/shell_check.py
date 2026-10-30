import asyncio,json
from localagent.base import Store,ROOT,write_json
from localagent.codex import Codex
from localagent.tools import Tools

async def main():
    result=await Tools(Store(),Codex(),None).shell('shell-path-check',{'script':"Write-Output 'POWERSHELL_PATH_OK'; Write-Output 'Кириллица работает'"})
    assert result['exit_code']==0 and 'POWERSHELL_PATH_OK' in result['stdout'] and 'Кириллица работает' in result['stdout']
    write_json(ROOT/'artifacts'/'powershell-check.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':asyncio.run(main())
