from llama_deploy.services.workflow import (
    WorkflowServiceConfig,
)


def test_config_creation() -> None:
    """Test basic config creation."""
    config = WorkflowServiceConfig(
        host="localhost", port=8000, service_name="test_service"
    )
    assert config.host == "localhost"
    assert config.port == 8000
    assert config.service_name == "test_service"


def test_config_defaults() -> None:
    """Test default values."""
    config = WorkflowServiceConfig(host="localhost", port=8000)
    assert config.service_name == "default_workflow_service"
    assert config.description == "A service that wraps a llama-index workflow."
    assert config.step_interval == 0.1
    assert config.max_concurrent_tasks == 8
    assert config.raise_exceptions is False
    assert config.use_tls is False
    assert config.internal_host is None
    assert config.internal_port is None


def test_url_property_http() -> None:
    """Test URL property for HTTP."""
    config = WorkflowServiceConfig(host="localhost", port=8000, use_tls=False)
    assert config.url == "http://localhost:8000"


def test_url_property_https() -> None:
    """Test URL property for HTTPS."""
    config = WorkflowServiceConfig(host="localhost", port=8443, use_tls=True)
    assert config.url == "https://localhost:8443"
