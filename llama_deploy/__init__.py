import logging
import warnings

root_logger = logging.getLogger("llama_deploy")

formatter = logging.Formatter("%(levelname)s:%(name)s - %(message)s")
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

root_logger.setLevel(logging.INFO)
root_logger.propagate = True

warnings.warn(
    "llama-deploy is deprecated. Use llama-agents instead to serve workflows. "
    "See https://github.com/run-llama/workflows-py for more information.",
    DeprecationWarning,
    stacklevel=2,
)
