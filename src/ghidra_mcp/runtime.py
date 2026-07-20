"""PyGhidra JVM 与已打开程序的生命周期所有权。"""

from __future__ import annotations

from pathlib import Path
from threading import RLock
from types import ModuleType
from typing import Any
from uuid import uuid4


class WorkspaceError(RuntimeError):
    """程序工作区操作失败。"""


class GhidraRuntime:
    def __init__(self, install_dir: Path, *, pyghidra_module: ModuleType | Any | None = None) -> None:
        self.install_dir = install_dir.resolve()
        if pyghidra_module is None:
            import pyghidra

            pyghidra_module = pyghidra
        self.pyghidra = pyghidra_module
        self._launcher: object | None = None
        self._lock = RLock()

    def ensure_started(self) -> object:
        with self._lock:
            if self._launcher is None:
                if not self.install_dir.is_dir():
                    raise WorkspaceError(f"Ghidra 安装目录不存在：{self.install_dir}")
                self._launcher = self.pyghidra.start(install_dir=self.install_dir)
            return self._launcher


class ProgramWorkspace:
    def __init__(self, runtime: GhidraRuntime) -> None:
        self.runtime = runtime
        self._programs: dict[str, tuple[Any, Any]] = {}
        self._lock = RLock()

    def open(
        self,
        binary_path: Path,
        *,
        project_location: Path | None = None,
        project_name: str | None = None,
        analyze: bool = True,
    ) -> str:
        binary = binary_path.resolve()
        if not binary.is_file():
            raise WorkspaceError(f"输入二进制不存在：{binary}")
        self.runtime.ensure_started()
        context = self.runtime.pyghidra.open_program(
            binary,
            project_location=project_location,
            project_name=project_name,
            analyze=analyze,
        )
        api = context.__enter__()
        program_id = uuid4().hex
        with self._lock:
            self._programs[program_id] = (context, api)
        return program_id

    def get(self, program_id: str) -> Any:
        with self._lock:
            try:
                return self._programs[program_id][1]
            except KeyError as error:
                raise WorkspaceError(f"程序会话不存在：{program_id}") from error

    def close(self, program_id: str) -> None:
        with self._lock:
            try:
                context, _ = self._programs.pop(program_id)
            except KeyError as error:
                raise WorkspaceError(f"程序会话不存在：{program_id}") from error
        context.__exit__(None, None, None)

    def close_all(self) -> None:
        with self._lock:
            program_ids = tuple(self._programs)
        for program_id in program_ids:
            self.close(program_id)
