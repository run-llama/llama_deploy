from string import Formatter
from typing import List


def get_prompt_params(prompt_template_str: str) -> List[str]:
    """Get the list of prompt params from the template format string."""
    return [param for _, param, _, _ in Formatter().parse(prompt_template_str) if param]
