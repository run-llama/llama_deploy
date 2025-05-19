import os
import shutil
import subprocess
from pathlib import Path

import uvicorn
from prometheus_client import start_http_server

from llama_deploy.apiserver import settings

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
    repo_url = source
    if token:
        repo_url = repo_url.replace("https://", f"https://{token}@")

    dest_dir = work_dir / CLONED_REPO_FOLDER

    if not dest_dir.exists() or force:
        run_process(
            ["git", "clone", "--depth", "1", repo_url, str(dest_dir.absolute())]
        )
    else:
        run_process(["git", "pull", "origin", "main"], cwd=str(dest_dir.absolute()))


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
    if not repo_url.startswith("https://"):
        raise ValueError("Git remote must be valid and over HTTPS")
    repo_token = os.environ.get("GITHUB_PAT")
    work_dir = Path(os.environ.get("WORK_DIR", RC_PATH))
    work_dir.mkdir(exist_ok=True, parents=True)

    setup_repo(work_dir, repo_url, repo_token)

    deployment_file_path = os.environ.get("DEPLOYMENT_FILE_PATH", "deployment.yml")
    deployment_file_abspath = work_dir / CLONED_REPO_FOLDER / deployment_file_path

    if not deployment_file_abspath.exists():
        raise ValueError(f"File {deployment_file_abspath} does not exist")

    copy_sources(work_dir, deployment_file_abspath)
    shutil.rmtree(work_dir / CLONED_REPO_FOLDER)

    # Ready to go
    os.environ["LLAMA_DEPLOY_APISERVER_RC_PATH"] = str(work_dir)
    uvicorn.run(
        "llama_deploy.apiserver:app",
        host=settings.host,
        port=settings.port,
    )
