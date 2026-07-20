"""Ghidra 写操作的原子事务边界。"""

from contextlib import contextmanager
from typing import Any, Iterator


@contextmanager
def program_transaction(program: Any, description: str) -> Iterator[None]:
    transaction_id = program.startTransaction(description)
    commit = False
    try:
        yield
        commit = True
    finally:
        program.endTransaction(transaction_id, commit)
