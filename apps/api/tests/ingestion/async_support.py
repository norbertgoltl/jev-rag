import asyncio
import functools
from collections.abc import Callable, Coroutine
from typing import Any


def async_test[**P](test: Callable[P, Coroutine[Any, Any, None]]) -> Callable[P, None]:
    """Run an ``async def`` test on a fresh event loop. The suite has no asyncio plugin."""

    @functools.wraps(test)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        asyncio.run(test(*args, **kwargs))

    return wrapper
