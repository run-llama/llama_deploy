import asyncio
import time
import numpy as np
import functools
from typing import Any, Callable

from logging import getLogger

logger = getLogger(__name__)


def exponential_delay(exponential_rate: float) -> Callable:
    """Wrapper for exponential tool."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> str:
            # random delay
            delay = np.random.exponential(exponential_rate)
            logger.info(f"waiting for {delay} seconds")
            time.sleep(delay)
            return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> str:
            # random delay
            delay = np.random.exponential(exponential_rate)
            logger.info(f"waiting for {delay} seconds")
            # await asyncio.sleep(delay)
            return await func(*args, **kwargs)

        return async_wrapper if asyncio.iscoroutinefunction(func) else wrapper

    return decorator


async def main() -> None:
    @exponential_delay(2)
    async def get_the_secret_fact() -> str:
        """Returns the secret fact."""
        return "The secret fact is: A baby llama is called a 'Cria'."

    @exponential_delay(1)
    async def async_correct_first_character(input: str) -> str:
        """Corrects the first character."""
        tokens = input.split()
        return " ".join([t[-1] + t[0:-1] for t in tokens])

    @exponential_delay(0.5)
    async def async_remove_ay_suffix(input: str) -> str:
        """Removes 'ay' suffix from each token in the input_sentence.

        Params:
            input_sentence (str): The input sentence i.e., sequence of words
        """
        logger.info(f"received task input: {input}")
        tokens = input.split()
        res = " ".join([t[:-2] for t in tokens])
        logger.info(f"Removed 'ay' suffix: {res}")
        return res

    output = await async_remove_ay_suffix(input="eyhay ouyay")

    print(output)
    print(async_remove_ay_suffix.__doc__)


if __name__ == "__main__":
    asyncio.run(main())
