"""Ghidra 写操作的原子事务边界。"""

from contextlib import contextmanager
from collections.abc import Callable, Iterator
from typing import Any


@contextmanager
def program_transaction(
    program: Any,
    description: str,
    *,
    persist: Callable[[], None] | None = None,
) -> Iterator[None]:
    transaction_id = program.startTransaction(description)
    try:
        yield
    except BaseException:
        program.endTransaction(transaction_id, False)
        raise
    program.endTransaction(transaction_id, True)
    if persist is None:
        return
    try:
        persist()
    except BaseException:
        if not program.canUndo() or str(program.getUndoName()) != description:
            raise RuntimeError(f"持久化失败，且无法安全撤销事务：{description}") from None
        program.undo()
        raise
