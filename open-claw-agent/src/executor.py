import asyncio
import yaml
from pathlib import Path

class TaskRegistry:
    def __init__(self, tasks_path: Path):
        self.tasks_path = tasks_path
        self.reload()

    def reload(self):
        data = yaml.safe_load(self.tasks_path.read_text(encoding="utf-8"))
        self.tasks = data.get("tasks", {}) if isinstance(data, dict) else {}

    def list_tasks(self) -> list[tuple[str, str, bool]]:
        out = []
        for task_id, spec in self.tasks.items():
            desc = str(spec.get("description", ""))
            dangerous = bool(spec.get("dangerous", False))
            out.append((task_id, desc, dangerous))
        return sorted(out, key=lambda x: x[0])

    def get(self, task_id: str) -> dict | None:
        return self.tasks.get(task_id)

async def run_cmd(cmd: list[str], cwd: str | None = None, timeout: int = 300) -> tuple[int, str]:
    """
    Возвращает (returncode, output). output = stdout+stderr
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out_b, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "TIMEOUT"
    out = (out_b or b"").decode("utf-8", errors="replace")
    return proc.returncode, out
