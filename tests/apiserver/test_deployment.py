import asyncio
import json
import subprocess
import sys
from collections.abc import Generator
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from workflows import Context, Workflow
from workflows.handler import WorkflowHandler

from llama_deploy.apiserver.deployment import (
    SOURCE_MANAGERS,
    Deployment,
    DeploymentError,
    Manager,
)
from llama_deploy.apiserver.deployment_config_parser import (
    DeploymentConfig,
    ServiceSource,
    SourceType,
    SyncPolicy,
    UIService,
)


@pytest.fixture
def deployment_config() -> DeploymentConfig:
    return DeploymentConfig(  # type: ignore
        **{  # type: ignore
            "name": "test-deployment",
            "services": {},
        }
    )


@pytest.fixture
def mock_local_source_manager() -> Generator[mock.MagicMock, Any, None]:
    original = SOURCE_MANAGERS[SourceType.local]
    mock_sm = mock.MagicMock()
    # Make the mock class return itself when called, as the SOURCE_MANAGERS dict is a dict of factories
    mock_sm.return_value = mock_sm

    SOURCE_MANAGERS[SourceType.local] = mock_sm  # type: ignore
    yield mock_sm
    SOURCE_MANAGERS[SourceType.local] = original


def test_deployment_ctor(data_path: Path, mock_importlib: Any, tmp_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")
    with mock.patch("llama_deploy.apiserver.deployment.SOURCE_MANAGERS") as sm_dict:
        sm_dict["git"] = mock.MagicMock()
        d = Deployment(config=config, base_path=data_path, deployment_path=tmp_path)

        sm_dict["git"].return_value.sync.assert_called_once()
        assert d.name == "TestDeployment"
        assert d._deployment_path.name == "TestDeployment"
        assert len(d._workflow_services) == 1
        assert d.service_names == ["test-workflow"]
        assert d.client is not None
        assert d.default_service == "test-workflow"


def test_deployment_ctor_missing_service_path(data_path: Path, tmp_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")
    config.services["test-workflow"].import_path = None
    with pytest.raises(
        ValueError, match="path field in service definition must be set"
    ):
        Deployment(config=config, base_path=data_path, deployment_path=tmp_path)


def test_deployment_ctor_skip_default_service(
    data_path: Path, mock_importlib: Any, tmp_path: Path
) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")
    config.services["test-workflow2"] = deepcopy(config.services["test-workflow"])

    with mock.patch("llama_deploy.apiserver.deployment.SOURCE_MANAGERS") as sm_dict:
        sm_dict["git"] = mock.MagicMock()
        d = Deployment(config=config, base_path=data_path, deployment_path=tmp_path)
        assert len(d._workflow_services) == 2


def test_deployment_ctor_invalid_default_service(
    data_path: Path, mock_importlib: Any, caplog: Any, tmp_path: Path
) -> None:
    config = DeploymentConfig.from_yaml(data_path / "local.yaml")
    config.default_service = "does-not-exist"

    Deployment(config=config, base_path=data_path, deployment_path=tmp_path)
    assert (
        "Service with id 'does-not-exist' does not exist, cannot set it as default."
        in caplog.text
    )


def test_deployment_ctor_default_service(
    data_path: Path, mock_importlib: Any, tmp_path: Path
) -> None:
    config = DeploymentConfig.from_yaml(data_path / "local.yaml")
    config.default_service = "test-workflow"

    d = Deployment(config=config, base_path=data_path, deployment_path=tmp_path)
    assert d.default_service == "test-workflow"


def test__install_dependencies(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "python_dependencies.yaml")
    service_config = config.services["myworkflow"]
    with mock.patch("llama_deploy.apiserver.deployment.subprocess") as mocked_subp:
        # Assert the sub process cmd receives the list of dependencies
        Deployment._install_dependencies(service_config, data_path)
        called_args = [call.args[0] for call in mocked_subp.check_call.call_args_list]
        # first should've checked for uv
        assert called_args[0] == ["uv", "--version"]
        # then should install vanilla pip dependencies with uv
        assert called_args[1][:3] == ["uv", "pip", "install"]
        assert called_args[1][3].startswith("--prefix=")
        assert called_args[1][4:] == ["llama-index-core<1", "llama-index-llms-openai"]
        assert called_args[2:] == []

        # Assert the method doesn't do anything if the list of dependencies is empty
        mocked_subp.reset_mock()
        service_config.python_dependencies = []
        Deployment._install_dependencies(service_config, data_path)
        mocked_subp.check_call.assert_not_called()


def test__install_dependencies_kitchen_sink(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(
        data_path / "python_dependencies_kitchen_sink.yaml"
    )
    service_config = config.services["myworkflow"]
    with (
        mock.patch("llama_deploy.apiserver.deployment.subprocess") as mocked_subp,
        mock.patch("llama_deploy.apiserver.deployment.os.path.isfile") as mock_isfile,
    ):
        # Mock isfile to return True for the pyproject.toml path
        def isfile_side_effect(path: str) -> bool:
            print("isfile_side_effect", path)
            return str(path).endswith("foo/bar") or "requirements.txt" in str(path)

        mock_isfile.side_effect = isfile_side_effect

        # Assert the sub process cmd receives the list of dependencies
        Deployment._install_dependencies(service_config, data_path)
        called_args = mocked_subp.check_call.call_args_list
        # first should've checked for uv
        assert called_args[0].args[0] == ["uv", "--version"]
        # then should install all things with uv pip, including requirements.txt, regular libs, and paths, assumed to be pyproject.tomls
        assert called_args[1].args[0][4:] == [
            "test<1",
            "-r",
            str(data_path / "bar/requirements.txt"),
            "-e",
            str(data_path / "foo/bar/"),
        ]


def test__set_environment_variables(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "env_variables.yaml")
    service_config = config.services["myworkflow"]
    with mock.patch("llama_deploy.apiserver.deployment.os.environ") as mocked_osenviron:
        # Assert the sub process cmd receives the list of dependencies
        Deployment._set_environment_variables(service_config, root=data_path)
        mocked_osenviron.__setitem__.assert_has_calls(
            [
                mock.call("VAR_1", "x"),
                mock.call("VAR_2", "y"),
                mock.call("API_KEY", "123"),
            ]
        )


def test__install_dependencies_raises(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "python_dependencies.yaml")
    service_config = config.services["myworkflow"]
    error_class = subprocess.CalledProcessError
    error = error_class(1, "cmd", output=None, stderr="There was an error")

    def raise_pip_install_error(*args: Any, **kwargs: Any) -> None:
        if args[0] == ["uv", "--version"]:
            return
        raise error

    with mock.patch("llama_deploy.apiserver.deployment.subprocess") as mocked_subp:
        # Assert the proper exception is raised if the sub process errors out

        mocked_subp.CalledProcessError = error_class
        mocked_subp.check_call.side_effect = raise_pip_install_error
        with pytest.raises(
            DeploymentError,
            match="Unable to install service dependencies using command 'cmd': There was an error",
        ):
            Deployment._install_dependencies(service_config, data_path)


def test__install_dependencies_security_requirements_txt_path_traversal(
    data_path: Path,
) -> None:
    """Test that requirements.txt files outside source root are rejected."""
    config = DeploymentConfig.from_yaml(data_path / "python_dependencies.yaml")
    service_config = config.services["myworkflow"]
    # Try to use a requirements.txt file outside the source root
    service_config.python_dependencies = ["../../../etc/passwd/requirements.txt"]

    with pytest.raises(
        DeploymentError,
        match="requirements file .* is not a subdirectory of the source root",
    ):
        Deployment._install_dependencies(service_config, data_path)


def test__install_dependencies_security_dependency_path_traversal(
    data_path: Path,
) -> None:
    """Test that dependency paths outside source root are rejected."""
    config = DeploymentConfig.from_yaml(data_path / "python_dependencies.yaml")
    service_config = config.services["myworkflow"]
    # Try to use a path outside the source root
    service_config.python_dependencies = ["../../../etc/passwd/"]

    with pytest.raises(
        DeploymentError,
        match="dependency path .* is not a subdirectory of the source root",
    ):
        Deployment._install_dependencies(service_config, data_path)


def test__validate_path_is_safe_valid_paths(tmp_path: Path) -> None:
    """Test that valid paths within source root are accepted."""
    # These should not raise exceptions
    Deployment._validate_path_is_safe("./subdir/file.txt", tmp_path, "test file")
    Deployment._validate_path_is_safe("subdir/file.txt", tmp_path, "test file")
    Deployment._validate_path_is_safe("file.txt", tmp_path, "test file")


def test__validate_path_is_safe_path_traversal_attacks(tmp_path: Path) -> None:
    """Test that path traversal attacks are blocked."""
    with pytest.raises(
        DeploymentError, match="test file .* is not a subdirectory of the source root"
    ):
        Deployment._validate_path_is_safe("../../../etc/passwd", tmp_path, "test file")

    with pytest.raises(
        DeploymentError, match="test file .* is not a subdirectory of the source root"
    ):
        Deployment._validate_path_is_safe("../../outside.txt", tmp_path, "test file")

    with pytest.raises(
        DeploymentError, match="test file .* is not a subdirectory of the source root"
    ):
        Deployment._validate_path_is_safe("../outside.txt", tmp_path, "test file")


def test__validate_path_is_safe_absolute_paths(tmp_path: Path) -> None:
    """Test that absolute paths outside source root are blocked."""
    with pytest.raises(
        DeploymentError, match="test file .* is not a subdirectory of the source root"
    ):
        Deployment._validate_path_is_safe("/etc/passwd", tmp_path, "test file")

    with pytest.raises(
        DeploymentError, match="test file .* is not a subdirectory of the source root"
    ):
        Deployment._validate_path_is_safe("/tmp/outside.txt", tmp_path, "test file")


def test__install_dependencies_uv_not_available_bootstrap_success(
    data_path: Path,
) -> None:
    """Test uv bootstrap when uv is not initially available but pip install succeeds."""
    config = DeploymentConfig.from_yaml(data_path / "python_dependencies.yaml")
    service_config = config.services["myworkflow"]

    def mock_check_call(*args: Any, **kwargs: Any) -> None:
        if args[0] == ["uv", "--version"]:
            # First call to check uv version fails
            raise subprocess.CalledProcessError(1, "uv --version")
        elif args[0][:4] == [sys.executable, "-m", "pip", "install"]:
            # pip install uv succeeds
            return
        elif args[0][:3] == ["uv", "pip", "install"]:
            # uv pip install succeeds after bootstrap
            return
        else:
            raise subprocess.CalledProcessError(1, str(args[0]))

    with mock.patch("llama_deploy.apiserver.deployment.subprocess") as mocked_subp:
        mocked_subp.CalledProcessError = subprocess.CalledProcessError
        mocked_subp.check_call.side_effect = mock_check_call
        mocked_subp.DEVNULL = subprocess.DEVNULL

        # Should not raise an exception
        Deployment._install_dependencies(service_config, data_path)

        # Verify the bootstrap sequence
        calls = mocked_subp.check_call.call_args_list
        assert len(calls) == 3
        # First: check uv version (fails)
        assert calls[0].args[0] == ["uv", "--version"]
        # Second: bootstrap uv with pip
        assert calls[1].args[0][:4] == [sys.executable, "-m", "pip", "install"]
        assert "uv" in calls[1].args[0]
        # Third: install dependencies with uv
        assert calls[2].args[0][:3] == ["uv", "pip", "install"]


def test__install_dependencies_uv_not_available_bootstrap_fails(
    data_path: Path,
) -> None:
    """Test uv bootstrap failure when pip install uv fails."""
    config = DeploymentConfig.from_yaml(data_path / "python_dependencies.yaml")
    service_config = config.services["myworkflow"]

    def mock_check_call(*args: Any, **kwargs: Any) -> None:
        if args[0] == ["uv", "--version"]:
            # uv not available
            raise subprocess.CalledProcessError(1, "uv --version")
        elif args[0][:4] == [sys.executable, "-m", "pip", "install"]:
            # pip install uv fails
            error = subprocess.CalledProcessError(
                1, "pip install uv", stderr="Bootstrap failed"
            )
            raise error
        else:
            raise subprocess.CalledProcessError(1, str(args[0]))

    with mock.patch("llama_deploy.apiserver.deployment.subprocess") as mocked_subp:
        mocked_subp.CalledProcessError = subprocess.CalledProcessError
        mocked_subp.check_call.side_effect = mock_check_call
        mocked_subp.DEVNULL = subprocess.DEVNULL

        with pytest.raises(
            DeploymentError,
            match="Unable to install uv. Environment must include uv, or uv must be installed with pip:",
        ):
            Deployment._install_dependencies(service_config, data_path)


def test__install_dependencies_uv_not_available_file_not_found(data_path: Path) -> None:
    """Test when uv command is not found at all."""
    config = DeploymentConfig.from_yaml(data_path / "python_dependencies.yaml")
    service_config = config.services["myworkflow"]

    def mock_check_call(*args: Any, **kwargs: Any) -> None:
        if args[0] == ["uv", "--version"]:
            # uv command not found
            raise FileNotFoundError("uv command not found")
        elif args[0][:4] == [sys.executable, "-m", "pip", "install"]:
            # pip install uv succeeds
            return
        elif args[0][:3] == ["uv", "pip", "install"]:
            # uv pip install succeeds after bootstrap
            return
        else:
            raise subprocess.CalledProcessError(1, str(args[0]))

    with mock.patch("llama_deploy.apiserver.deployment.subprocess") as mocked_subp:
        mocked_subp.CalledProcessError = subprocess.CalledProcessError
        mocked_subp.check_call.side_effect = mock_check_call
        mocked_subp.DEVNULL = subprocess.DEVNULL

        # Should not raise an exception, should bootstrap uv
        Deployment._install_dependencies(service_config, data_path)

        # Verify the bootstrap sequence
        calls = mocked_subp.check_call.call_args_list
        assert len(calls) == 3
        # First: check uv version (FileNotFoundError)
        assert calls[0].args[0] == ["uv", "--version"]
        # Second: bootstrap uv with pip
        assert calls[1].args[0][:4] == [sys.executable, "-m", "pip", "install"]
        # Third: install dependencies with uv
        assert calls[2].args[0][:3] == ["uv", "pip", "install"]


def test__install_dependencies_mixed_path_types(
    data_path: Path, tmp_path: Path
) -> None:
    """Test handling of mixed dependency types including paths with different separators."""
    config = DeploymentConfig.from_yaml(data_path / "python_dependencies.yaml")
    service_config = config.services["myworkflow"]

    # Create test files in the source root
    test_req_file = tmp_path / "test_requirements.txt"
    test_req_file.write_text("requests>=2.0.0\n")
    test_pyproject_dir = tmp_path / "test_project"
    test_pyproject_dir.mkdir()
    (test_pyproject_dir / "pyproject.toml").write_text("[project]\nname = 'test'\n")

    # Mix of different dependency types
    service_config.python_dependencies = [
        "regular-package>=1.0.0",  # Regular package
        "./test_requirements.txt",  # Requirements file
        "./test_project/",  # Directory with pyproject.toml
        "package-with-version<2.0",  # Package with version constraint
    ]

    with (
        mock.patch("llama_deploy.apiserver.deployment.subprocess") as mocked_subp,
        mock.patch("llama_deploy.apiserver.deployment.os.path.isfile") as mock_isfile,
    ):

        def isfile_side_effect(path: str) -> bool:
            return str(path).endswith("test_project") or "test_requirements.txt" in str(
                path
            )

        mock_isfile.side_effect = isfile_side_effect

        Deployment._install_dependencies(service_config, tmp_path)

        calls = mocked_subp.check_call.call_args_list
        # Should have uv version check and install command
        assert len(calls) == 2
        assert calls[0].args[0] == ["uv", "--version"]

        # Check the install arguments
        install_args = calls[1].args[0][4:]  # Skip "uv pip install --prefix=..."
        expected_args = [
            "regular-package>=1.0.0",
            "-r",
            str(tmp_path / "test_requirements.txt"),
            "-e",
            str(tmp_path / "test_project/"),
            "package-with-version<2.0",
        ]
        assert install_args == expected_args


def test_manager_ctor() -> None:
    m = Manager()
    m.set_deployments_path(None)
    assert m.deployments_path.name == "deployments"
    assert m._max_deployments == 10

    m = Manager(max_deployments=42)
    m.set_deployments_path(None)
    assert m.deployments_path.name == "deployments"
    assert m._max_deployments == 42


@pytest.mark.asyncio
async def test_manager_deploy_duplicate(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")

    m = Manager()
    m._serving = True
    m._deployments["TestDeployment"] = mock.MagicMock()

    with pytest.raises(ValueError, match="Deployment already exists: TestDeployment"):
        await m.deploy(config, base_path=str(data_path))


@pytest.mark.asyncio
async def test_manager_deploy_maximum_reached(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")

    m = Manager(max_deployments=1)
    m._serving = True
    m._deployments["AnotherDeployment"] = mock.MagicMock()

    with pytest.raises(
        ValueError,
        match="Reached the maximum number of deployments, cannot schedule more",
    ):
        await m.deploy(config, base_path="")


@pytest.mark.asyncio
async def test_manager_deploy(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")

    with mock.patch(
        "llama_deploy.apiserver.deployment.Deployment"
    ) as mocked_deployment:
        # Mock the start method as an async method
        mocked_deployment.return_value.start = mock.AsyncMock()

        m = Manager()
        m._serving = True
        m._deployments_path = Path()
        await m.deploy(config, base_path=str(data_path))
        mocked_deployment.assert_called_once()
        mocked_deployment.return_value.start.assert_awaited_once()
        assert m.deployment_names == ["TestDeployment"]
        assert m.get_deployment("TestDeployment") is not None


@pytest.mark.asyncio
async def test_manager_serve_loop(tmp_path: Path) -> None:
    m = Manager()
    m.set_deployments_path(tmp_path)
    serve_task = asyncio.create_task(m.serve())
    # Allow the serve task to start
    await asyncio.sleep(0)

    # Check that the task is still running
    assert not serve_task.done()

    # Cancel the task
    serve_task.cancel()
    await serve_task
    assert serve_task.done()
    assert serve_task.exception() is None


@pytest.mark.asyncio
async def test_start_sequence(
    deployment_config: DeploymentConfig, tmp_path: Path
) -> None:
    deployment = Deployment(
        config=deployment_config, base_path=Path(), deployment_path=tmp_path
    )
    deployment._start_ui_server = mock.AsyncMock()  # type: ignore
    await deployment.start()
    # no ui server
    deployment._start_ui_server.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_with_services(data_path: Path, tmp_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")
    with mock.patch("llama_deploy.apiserver.deployment.SOURCE_MANAGERS") as sm_dict:
        deployment = Deployment(
            config=config, base_path=data_path, deployment_path=tmp_path
        )
        deployment._start_ui_server = mock.AsyncMock(return_value=[])  # type: ignore

        sm_dict["git"] = mock.MagicMock()
        await deployment.start()
        sm_dict["git"].return_value.sync.assert_called_once()

    # Verify UI server was not started
    deployment._start_ui_server.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_with_services_ui(data_path: Path, tmp_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")
    config.ui = mock.MagicMock()
    with mock.patch("llama_deploy.apiserver.deployment.SOURCE_MANAGERS") as sm_dict:
        deployment = Deployment(
            config=config, base_path=data_path, deployment_path=tmp_path
        )
        deployment._start_ui_server = mock.AsyncMock(return_value=[])  # type: ignore

        sm_dict["git"] = mock.MagicMock()
        await deployment.start()

    deployment._start_ui_server.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_ui_server_success(data_path: Path, tmp_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "with_ui.yaml")
    deployment = Deployment(
        config=config, base_path=data_path, deployment_path=tmp_path
    )

    # Mock the necessary components
    with (
        mock.patch("llama_deploy.apiserver.deployment.SOURCE_MANAGERS") as sm_dict,
        mock.patch(
            "llama_deploy.apiserver.deployment.asyncio.create_subprocess_exec"
        ) as mock_subprocess,
        mock.patch("llama_deploy.apiserver.deployment.os") as mock_os,
    ):
        # Configure source manager mock
        source_manager_mock = mock.MagicMock()
        sm_dict.__getitem__.return_value.return_value = source_manager_mock

        # Configure subprocess mock
        process_mock = mock.AsyncMock()
        process_mock.pid = 12345
        mock_subprocess.return_value = process_mock
        process_mock.wait.return_value = 0

        # Configure os environment
        mock_os.environ.copy.return_value = {"PATH": "/some/path"}

        # Run the method
        await deployment._start_ui_server()

        # Verify source manager was used correctly
        source_manager_mock.sync.assert_called_once()

        # Verify npm commands were executed
        assert mock_subprocess.call_count == 2
        # First call should be npm ci
        assert mock_subprocess.call_args_list[0][0][:2] == ("pnpm", "install")
        # Second call should be npm run dev
        assert mock_subprocess.call_args_list[1][0][:3] == ("pnpm", "run", "dev")

        # Verify environment variables were set
        assert mock_os.environ.copy.called
        env = mock_subprocess.call_args_list[1][1]["env"]
        assert env["LLAMA_DEPLOY_NEXTJS_BASE_PATH"] == "/deployments/test-deployment/ui"
        assert env["LLAMA_DEPLOY_NEXTJS_DEPLOYMENT_NAME"] == "test-deployment"


@pytest.mark.asyncio
async def test_start_ui_server_missing_config(
    deployment_config: DeploymentConfig, tmp_path: Path
) -> None:
    """Test that _start_ui_server raises appropriate error when UI config is missing."""
    deployment_config.ui = None
    deployment = Deployment(
        config=deployment_config, base_path=Path(), deployment_path=tmp_path
    )

    with pytest.raises(ValueError, match="missing ui configuration settings"):
        await deployment._start_ui_server()


@pytest.mark.asyncio
async def test_merges_in_path_to_installation(
    deployment_config: DeploymentConfig, tmp_path: Path
) -> None:
    """Test that _start_ui_server raises appropriate error when source is missing."""
    deployment_config.ui = mock.MagicMock(source=None)
    deployment = Deployment(
        config=deployment_config, base_path=Path(), deployment_path=tmp_path
    )

    with pytest.raises(ValueError, match="source must be defined"):
        await deployment._start_ui_server()


@pytest.mark.asyncio
async def test_start_ui_server_uses_merge_sync_policy(
    deployment_config: DeploymentConfig,
    tmp_path: Path,
    mock_local_source_manager: mock.MagicMock,
) -> None:
    """Test that _start_ui_server syncs into the correct directory, and starts services there"""
    # Setup a mock source with sync_policy set to MERGE
    mock_source = ServiceSource(
        type=SourceType.local,
        location="some/location",
        sync_policy=SyncPolicy.MERGE,
    )
    deployment_config.ui = UIService.model_validate(
        {
            "name": "test-ui",
            "source": mock_source,
        }
    )
    # Patch SOURCE_MANAGERS to return a mock source manager
    mock_local_source_manager.relative_path = mock.MagicMock()
    mock_local_source_manager.relative_path.return_value = "some/location"

    # Patch subprocess and os
    mock_subprocess = mock.AsyncMock()
    with mock.patch("asyncio.create_subprocess_exec", mock_subprocess):
        mock_subprocess.return_value.wait = mock.AsyncMock()
        mock_subprocess.return_value.pid = 1234

        deployment = Deployment(
            config=deployment_config, base_path=Path(), deployment_path=tmp_path
        )

        await deployment._start_ui_server()

        # Check that sync was called with SyncPolicy.MERGE
        assert mock_local_source_manager.sync.call_count == 1
        args, kwargs = mock_local_source_manager.sync.call_args
        # The third argument is the policy
        assert args[2] == SyncPolicy.MERGE
        # verify that the relative path was used for the commands
        installed_path = tmp_path / "test-deployment" / "some/location"
        # The first call to create_subprocess_exec should be for "pnpm", "install"
        install_call = mock_subprocess.call_args_list[0]
        assert install_call.args[:2] == ("pnpm", "install")
        assert install_call.kwargs["cwd"] == installed_path

        # The second call to create_subprocess_exec should be for "pnpm", "run", "dev"
        run_call = mock_subprocess.call_args_list[1]
        assert run_call.args[:3] == ("pnpm", "run", "dev")
        assert run_call.kwargs["cwd"] == installed_path


@pytest.mark.asyncio
async def test_run_workflow_without_session_without_kwargs(
    deployment_config: DeploymentConfig, tmp_path: Path
) -> None:
    """Test run_workflow with no session_id and no run_kwargs."""
    deployment = Deployment(
        config=deployment_config, base_path=Path(), deployment_path=tmp_path
    )

    # Mock workflow
    mock_workflow = mock.MagicMock(spec=Workflow)
    mock_workflow.run = mock.AsyncMock(return_value="test_result")
    deployment._workflow_services = {"test_service": mock_workflow}

    result = await deployment.run_workflow("test_service")

    assert result == "test_result"
    mock_workflow.run.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_run_workflow_without_session_with_kwargs(
    deployment_config: DeploymentConfig, tmp_path: Path
) -> None:
    """Test run_workflow with no session_id but with run_kwargs."""
    deployment = Deployment(
        config=deployment_config, base_path=Path(), deployment_path=tmp_path
    )

    # Mock workflow
    mock_workflow = mock.MagicMock(spec=Workflow)
    mock_workflow.run = mock.AsyncMock(return_value="test_result_with_kwargs")
    deployment._workflow_services = {"test_service": mock_workflow}

    test_kwargs = {"input": "test_input", "param": 42}
    result = await deployment.run_workflow("test_service", **test_kwargs)  # type:ignore

    assert result == "test_result_with_kwargs"
    mock_workflow.run.assert_awaited_once_with(**test_kwargs)


@pytest.mark.asyncio
async def test_run_workflow_with_session_id(
    deployment_config: DeploymentConfig, tmp_path: Path
) -> None:
    """Test run_workflow with session_id."""
    deployment = Deployment(
        config=deployment_config, base_path=Path(), deployment_path=tmp_path
    )

    # Mock workflow and context
    mock_workflow = mock.MagicMock(spec=Workflow)
    mock_workflow.run = mock.AsyncMock(return_value="test_result_with_session")
    mock_context = mock.MagicMock(spec=Context)

    deployment._workflow_services = {"test_service": mock_workflow}
    deployment._contexts = {"test_session": mock_context}

    test_kwargs = {"input": "session_test"}
    result = await deployment.run_workflow(
        "test_service",
        "test_session",
        **test_kwargs,  # type:ignore
    )

    assert result == "test_result_with_session"
    mock_workflow.run.assert_awaited_once_with(context=mock_context, **test_kwargs)


def test_run_workflow_no_wait_without_session_id(
    deployment_config: DeploymentConfig, tmp_path: Path
) -> None:
    """Test run_workflow_no_wait without session_id."""
    deployment = Deployment(
        config=deployment_config, base_path=Path(), deployment_path=tmp_path
    )

    # Mock workflow and handler
    mock_workflow = mock.MagicMock(spec=Workflow)
    mock_handler = mock.MagicMock(spec=WorkflowHandler)
    mock_context = mock.MagicMock(spec=Context)
    mock_handler.ctx = mock_context
    mock_workflow.run.return_value = mock_handler

    deployment._workflow_services = {"test_service": mock_workflow}

    test_kwargs = {"input": "test_input", "param": 42}

    with mock.patch(
        "llama_deploy.apiserver.deployment.generate_id"
    ) as mock_generate_id:
        mock_generate_id.side_effect = ["session_456", "handler_123"]

        handler_id, session_id = deployment.run_workflow_no_wait(
            "test_service",
            None,
            **test_kwargs,  # type:ignore
        )

        assert handler_id == "handler_123"
        assert session_id == "session_456"
        assert deployment._handlers["handler_123"] == mock_handler
        assert deployment._contexts["session_456"] == mock_context
        assert deployment._handler_inputs["handler_123"] == json.dumps(test_kwargs)

        mock_workflow.run.assert_called_once_with(**test_kwargs)


def test_run_workflow_no_wait_with_session_id(
    deployment_config: DeploymentConfig, tmp_path: Path
) -> None:
    """Test run_workflow_no_wait with existing session_id."""
    deployment = Deployment(
        config=deployment_config, base_path=Path(), deployment_path=tmp_path
    )

    # Mock workflow, handler, and context
    mock_workflow = mock.MagicMock(spec=Workflow)
    mock_handler = mock.MagicMock(spec=WorkflowHandler)
    mock_context = mock.MagicMock(spec=Context)
    mock_workflow.run.return_value = mock_handler

    deployment._workflow_services = {"test_service": mock_workflow}
    deployment._contexts = {"existing_session": mock_context}

    test_kwargs = {"input": "session_test", "value": 100}

    with mock.patch(
        "llama_deploy.apiserver.deployment.generate_id"
    ) as mock_generate_id:
        mock_generate_id.return_value = "handler_789"

        handler_id, session_id = deployment.run_workflow_no_wait(
            "test_service",
            "existing_session",
            **test_kwargs,  # type:ignore
        )

        assert handler_id == "handler_789"
        assert session_id == "existing_session"
        assert deployment._handlers["handler_789"] == mock_handler
        assert deployment._handler_inputs["handler_789"] == json.dumps(test_kwargs)

        # Context should not be modified since session existed
        assert deployment._contexts["existing_session"] == mock_context

        mock_workflow.run.assert_called_once_with(context=mock_context, **test_kwargs)


def test_run_workflow_no_wait_empty_kwargs(
    deployment_config: DeploymentConfig, tmp_path: Path
) -> None:
    """Test run_workflow_no_wait with empty run_kwargs."""
    deployment = Deployment(
        config=deployment_config, base_path=Path(), deployment_path=tmp_path
    )

    # Mock workflow and handler
    mock_workflow = mock.MagicMock(spec=Workflow)
    mock_handler = mock.MagicMock(spec=WorkflowHandler)
    mock_context = mock.MagicMock(spec=Context)
    mock_handler.ctx = mock_context
    mock_workflow.run.return_value = mock_handler

    deployment._workflow_services = {"test_service": mock_workflow}

    with mock.patch(
        "llama_deploy.apiserver.deployment.generate_id"
    ) as mock_generate_id:
        mock_generate_id.side_effect = ["session_empty", "handler_empty"]

        handler_id, session_id = deployment.run_workflow_no_wait("test_service")

        assert handler_id == "handler_empty"
        assert session_id == "session_empty"
        assert deployment._handlers["handler_empty"] == mock_handler
        assert deployment._contexts["session_empty"] == mock_context
        assert deployment._handler_inputs["handler_empty"] == json.dumps({})

        mock_workflow.run.assert_called_once_with()


@pytest.mark.asyncio
async def test_run_workflow_service_not_found(
    deployment_config: DeploymentConfig, tmp_path: Path
) -> None:
    """Test run_workflow raises KeyError when service not found."""
    deployment = Deployment(
        config=deployment_config, base_path=Path(), deployment_path=tmp_path
    )

    deployment._workflow_services = {}

    with pytest.raises(KeyError):
        await deployment.run_workflow("nonexistent_service")


def test_run_workflow_no_wait_service_not_found(
    deployment_config: DeploymentConfig, tmp_path: Path
) -> None:
    """Test run_workflow_no_wait raises KeyError when service not found."""
    deployment = Deployment(
        config=deployment_config, base_path=Path(), deployment_path=tmp_path
    )

    deployment._workflow_services = {}

    with pytest.raises(KeyError):
        deployment.run_workflow_no_wait("nonexistent_service")


@pytest.mark.asyncio
async def test_run_workflow_session_not_found(
    deployment_config: DeploymentConfig, tmp_path: Path
) -> None:
    """Test run_workflow raises KeyError when session not found."""
    deployment = Deployment(
        config=deployment_config, base_path=Path(), deployment_path=tmp_path
    )

    # Mock workflow
    mock_workflow = mock.MagicMock(spec=Workflow)
    mock_workflow.run = mock.AsyncMock()
    deployment._workflow_services = {"test_service": mock_workflow}
    deployment._contexts = {}

    with pytest.raises(KeyError):
        await deployment.run_workflow("test_service", "nonexistent_session")
