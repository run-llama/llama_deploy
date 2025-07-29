import os
import shutil
import subprocess
from pathlib import Path

import uvicorn
import yaml
from prometheus_client import start_http_server

from llama_deploy.apiserver.settings import settings

CLONED_REPO_FOLDER = Path("cloned_repo")
RC_PATH = Path("/data")


def run_process(args: list[str], cwd: str | None = None) -> None:
    kwargs = {
        "args": args,
        "capture_output": True,
        "text": True,
        "check": False,
    }
    if cwd:
        kwargs["cwd"] = cwd
    process = subprocess.run(**kwargs)  # type: ignore
    if process.returncode != 0:
        stderr = process.stderr or ""
        raise Exception(stderr)


def setup_repo(
    work_dir: Path, source: str, token: str | None = None, force: bool = False
) -> None:
    repo_url, ref_name = _parse_source(source, token)
    dest_dir = work_dir / CLONED_REPO_FOLDER

    # Remove existing repo if force=True
    if dest_dir.exists() and force:
        shutil.rmtree(dest_dir)

    if not dest_dir.exists():
        # need to do a full clone to resolve any kind of ref without exploding in
        # complexity (tag, branch, commit, short commit)
        clone_args = ["git", "clone", repo_url, str(dest_dir.absolute())]
        run_process(clone_args, cwd=str(work_dir.absolute()))
    else:
        run_process(["git", "fetch", "origin"], cwd=str(dest_dir.absolute()))

    # Checkout the ref (let git resolve it)
    if ref_name:
        run_process(["git", "checkout", ref_name], cwd=str(dest_dir.absolute()))
    # If no ref specified, stay on whatever the clone gave us (default branch)


def _is_valid_uri(uri: str) -> bool:
    """Check if string looks like a valid URI"""
    return "://" in uri and "/" in uri.split("://", 1)[1]


def _parse_source(source: str, pat: str | None = None) -> tuple[str, str | None]:
    """Accept Github urls like https://github.com/run-llama/llama_deploy.git@main
    or https://user:token@github.com/run-llama/llama_deploy.git@v1.0.0
    Returns the final URL (with auth if needed) and ref name (branch, tag, or commit SHA)"""

    # Try splitting on last @ to see if we have a ref specifier
    url = source
    ref_name = None

    if "@" in source:
        potential_url, potential_ref = source.rsplit("@", 1)
        if _is_valid_uri(potential_url):
            url = potential_url
            ref_name = potential_ref

    # Inject PAT auth if provided and URL doesn't already have auth
    if pat and "://" in url and "@" not in url:
        url = url.replace("https://", f"https://{pat}@")

    return url, ref_name


def copy_sources(work_dir: Path, deployment_file_path: Path) -> None:
    app_folder = deployment_file_path.parent
    for item in app_folder.iterdir():
        if item.is_dir():
            # For directories, use copytree with dirs_exist_ok=True
            shutil.copytree(
                item, f"{work_dir.absolute()}/{item.name}", dirs_exist_ok=True
            )
        else:
            # For files, use copy2 to preserve metadata
            shutil.copy2(item, str(work_dir))


if __name__ == "__main__":
    if settings.prometheus_enabled:
        start_http_server(settings.prometheus_port)

    repo_url = os.environ.get("REPO_URL", "")
    if not repo_url.startswith("https://") and not repo_url.startswith("http://"):
        raise ValueError("Git remote must HTTP(S)")
    repo_token = os.environ.get("GITHUB_PAT")
    work_dir = Path(os.environ.get("WORK_DIR", RC_PATH))
    work_dir.mkdir(exist_ok=True, parents=True)

    setup_repo(work_dir, repo_url, repo_token)

    if not settings.deployment_file_path:
        # first fall back to none LLAMA_DEPLOY_APISERVER_ prefixed env var (settings requires the prefix)
        settings.deployment_file_path = os.environ.get(
            "DEPLOYMENT_FILE_PATH", "deployment.yml"
        )
    deployment_file_path = settings.deployment_file_path
    deployment_file_abspath = work_dir / CLONED_REPO_FOLDER / deployment_file_path
    if not deployment_file_abspath.exists():
        raise ValueError(f"File {deployment_file_abspath} does not exist")

    deployment_override_name = os.environ.get("DEPLOYMENT_NAME")
    if deployment_override_name:
        with open(deployment_file_abspath) as f:
            # Replace deployment name with the overridden value
            data = yaml.safe_load(f)

        # Avoid failing here if the deployment config file has a wrong format,
        # let's do nothing if there's no field `name`
        if "name" in data:
            data["name"] = deployment_override_name
            with open(deployment_file_abspath, "w") as f:
                yaml.safe_dump(data, f)

    copy_sources(work_dir, deployment_file_abspath)
    shutil.rmtree(work_dir / CLONED_REPO_FOLDER)

    # update rc_path directly, as it has already been loaded, so setting the environment variable
    # doesn't work
    settings.rc_path = work_dir
    uvicorn.run(
        "llama_deploy.apiserver.app:app",
        host=settings.host,
        port=settings.port,
    )
