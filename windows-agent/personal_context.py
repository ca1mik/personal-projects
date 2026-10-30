"""Read-only context for the scheduled personal briefing in the bound Codex chat."""
import json
from localagent.base import Store
from localagent.personal import context

if __name__=='__main__':print(json.dumps(context(Store()),ensure_ascii=False,indent=2))
