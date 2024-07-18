import os


def load_from_env(var: str) -> str:
    try:
        res = os.environ[var]
    except KeyError:
        raise ValueError(f"Missing env var '{var}'.")
    return res
