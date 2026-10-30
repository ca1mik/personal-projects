from __future__ import annotations

from dataclasses import asdict
import json
import os
import subprocess

import httpx

from apps.api.app.config import get_settings
from workers.common.errors import AdapterExecutionError
from workers.common.models import AdapterResult, JobContext
from workers.common.placeholders import collect_standard_outputs, create_stub_outputs


class HunyuanMultiViewAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.default_mode = os.getenv("HUNYUAN_MV_MODE", "stub").strip().lower()

    def resolve_mode(self, requested_mode: str | None) -> str:
        mode = (requested_mode or "auto").lower()
        if mode == "auto":
            mode = self.default_mode
        if mode not in {"stub", "http", "subprocess"}:
            raise AdapterExecutionError("HUNYUAN_MV_INVALID_MODE", f"Unsupported Hunyuan MV mode '{mode}'.")
        return mode

    def generate(self, job_context: JobContext) -> AdapterResult:
        mode = self.resolve_mode(job_context.params.get("execution_mode"))
        if mode == "stub":
            return create_stub_outputs(job_context, "Hunyuan3D-2MV Stub", self.settings.stub_multi_delay_seconds)
        if mode == "http":
            return self._generate_via_http(job_context)
        return self._generate_via_subprocess(job_context)

    def _generate_via_http(self, job_context: JobContext) -> AdapterResult:
        url = os.getenv("HUNYUAN_MV_HTTP_URL")
        if not url:
            raise AdapterExecutionError(
                "HUNYUAN_MV_HTTP_URL_MISSING",
                "Set HUNYUAN_MV_HTTP_URL before using Hunyuan MV in HTTP mode.",
            )

        payload = {
            "job_id": job_context.job_id,
            "input_files": [file.__dict__ for file in job_context.input_files],
            "input_dir": str(job_context.input_dir),
            "output_dir": str(job_context.output_dir),
        }

        try:
            with httpx.Client(timeout=float(os.getenv("HUNYUAN_MV_HTTP_TIMEOUT_SECONDS", "600"))) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AdapterExecutionError("HUNYUAN_MV_HTTP_FAILED", f"Hunyuan MV HTTP request failed: {exc}") from exc

        # TODO: Replace this generic contract with the real Hunyuan3D-2mv server contract.
        return collect_standard_outputs(job_context, generator_name="Hunyuan3D-2MV", mode="http")

    def _generate_via_subprocess(self, job_context: JobContext) -> AdapterResult:
        command_json = os.getenv("HUNYUAN_MV_SUBPROCESS_COMMAND_JSON")
        if not command_json:
            raise AdapterExecutionError(
                "HUNYUAN_MV_SUBPROCESS_COMMAND_MISSING",
                "Set HUNYUAN_MV_SUBPROCESS_COMMAND_JSON before using Hunyuan MV in subprocess mode.",
            )

        try:
            command = json.loads(command_json)
        except json.JSONDecodeError as exc:
            raise AdapterExecutionError(
                "HUNYUAN_MV_SUBPROCESS_COMMAND_INVALID",
                "HUNYUAN_MV_SUBPROCESS_COMMAND_JSON must be a JSON array of strings.",
            ) from exc

        if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
            raise AdapterExecutionError(
                "HUNYUAN_MV_SUBPROCESS_COMMAND_INVALID",
                "HUNYUAN_MV_SUBPROCESS_COMMAND_JSON must be a JSON array of strings.",
            )

        env = os.environ.copy()
        env.update(
            {
                "ENYA_JOB_ID": job_context.job_id,
                "ENYA_INPUT_DIR": str(job_context.input_dir),
                "ENYA_OUTPUT_DIR": str(job_context.output_dir),
                "ENYA_JOB_TYPE": job_context.job_type,
                "ENYA_BACKEND": job_context.backend,
                "ENYA_INPUT_FILES_JSON": json.dumps([asdict(file) for file in job_context.input_files]),
                "ENYA_JOB_PARAMS_JSON": json.dumps(job_context.params),
            }
        )

        completed = subprocess.run(
            command,
            cwd=self.settings.project_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise AdapterExecutionError(
                "HUNYUAN_MV_SUBPROCESS_FAILED",
                completed.stderr.strip() or completed.stdout.strip() or "Hunyuan MV subprocess exited with a non-zero status.",
            )

        # TODO: Replace ENYA_* env handoff with the real Hunyuan3D-2mv CLI integration.
        return collect_standard_outputs(job_context, generator_name="Hunyuan3D-2MV", mode="subprocess")


def generate_multiview_to_3d(job_context: JobContext) -> AdapterResult:
    return HunyuanMultiViewAdapter().generate(job_context)
