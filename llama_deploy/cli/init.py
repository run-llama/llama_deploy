import click
import os
import shutil
import subprocess
import tempfile
import yaml
from pathlib import Path
from typing import Any, Dict, Optional, List, Union, Type

# Import pydantic models
from llama_deploy.apiserver.deployment_config_parser import (
    DeploymentConfig, 
    MessageQueueConfig,
    ServiceSource, 
    Service,
    UIService, 
    SourceType
)
from llama_deploy.control_plane.server import ControlPlaneConfig
from llama_deploy.message_queues import (
    AWSMessageQueueConfig,
    KafkaMessageQueueConfig,
    RabbitMQMessageQueueConfig,
    RedisMessageQueueConfig,
    SimpleMessageQueueConfig,
    SolaceMessageQueueConfig,
)

SUPPORTED_MESSAGE_QUEUES: Dict[str, Type[MessageQueueConfig]] = {
    x.model_json_schema()["properties"]["type"]["default"]: x for x in [
        AWSMessageQueueConfig,
        KafkaMessageQueueConfig,
        RabbitMQMessageQueueConfig,
        RedisMessageQueueConfig,
        SimpleMessageQueueConfig,
        SolaceMessageQueueConfig,
    ]
}


@click.command()
@click.option(
    "--name",
    type=str,
    default=None,
    help="Name of the project to create",
)
@click.option(
    "--destination",
    type=str,
    default=None,
    help="Directory where the project will be created",
)
@click.option(
    "--port",
    type=int,
    default=None,
    help="Port for the control plane server",
)
@click.option(
    "--message-queue-type",
    type=click.Choice(["simple", "redis", "rabbitmq", "kafka", "aws", "solace"]),
    default=None,
    help="Type of message queue to use",
)
@click.option(
    "--template",
    type=click.Choice(["basic", "advanced"]),  # For future: add more templates
    default=None,
    help="Template to use for the workflow (currently only 'basic' is supported)",
)
def init(
    name: Optional[str] = None,
    destination: Optional[str] = None,
    port: Optional[int] = None,
    message_queue_type: Optional[str] = None,
    template: Optional[str] = None,
) -> None:
    """Bootstrap a new llama-deploy project with a basic workflow and configuration."""
    # Interactive walkthrough - get inputs if not provided via CLI
    if name is None:
        name = click.prompt("Project name", type=str)
    
    if destination is None:
        destination = click.prompt(
            "Destination directory",
            default=".",
            type=str,
            show_default=True,
        )
    
    if port is None:
        port = click.prompt(
            "Control plane port",
            default=8000,
            type=int,
            show_default=True,
        )
    
    if message_queue_type is None:        
        message_queue_type = click.prompt(
            "\nSelect message queue type",
            default="simple",
            type=click.Choice(SUPPORTED_MESSAGE_QUEUES.keys()),
            show_default=True,
        )
    
    if template is None:
        click.echo("\nWorkflow template:")
        click.echo("  basic     - Basic workflow with OpenAI integration (recommended)")
        click.echo("  chat      - A Chatbot workflow with OpenAI integration")
        click.echo("  none      - Do not create any sample workflow code (you just want a deployment.yml)")
        
        template = click.prompt(
            "\nSelect workflow template",
            default="basic",
            type=click.Choice(["basic", "chat", "none"]),
            show_default=True,
        )
    
    # Additional configuration options
    if template != "none":
        use_ui = click.confirm("\nWould you like to bundle a sample next.js UI with your deployment?", default=True)
    else:
        use_ui = False
    
    # Create project directory
    project_dir = Path(destination) / name
    if project_dir.exists():
        if not click.confirm(f"\nDirectory {project_dir} already exists. Continue?"):
            raise click.Abort()
    else:
        project_dir.mkdir(parents=True, exist_ok=True)
        click.echo(f"Created project directory: {project_dir}")

    # Create src directory for workflow code
    src_dir = project_dir / "src"
    src_dir.mkdir(exist_ok=True)
    
    # Create deployment.yml using pydantic models
    deployment_config = create_deployment_config(name, port, message_queue_type, use_ui)
    deployment_path = project_dir / "deployment.yml"
    write_yaml_with_comments(deployment_path, deployment_config.model_dump(exclude_none=True, by_alias=True))
    click.echo(f"Created deployment config: {deployment_path}")
    
    # Download the template from github
    if template != "none":
        template_url = f"https://github.com/run-llama/llama_deploy/tree/main/templates/{template}"

        # Create a temporary directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            # Clone only the specific directory (with depth=1 for efficiency)
            click.echo(f"Cloning template files from repository...")
            
            try:
                subprocess.run(
                    ["git", "clone", "--depth=1", "--filter=blob:none", "--sparse", template_url, temp_dir],
                    check=True,
                    capture_output=True
                )
                
                # Navigate to temp dir and set up sparse checkout
                os.chdir(temp_dir)
                subprocess.run(
                    ["git", "sparse-checkout", "set", f"templates/{template}"],
                    check=True,
                    capture_output=True
                )
                
                # Copy template files to the project
                template_dir = Path(temp_dir) / "templates" / template
                if not template_dir.exists():
                    raise FileNotFoundError(f"Template directory not found: {template_dir}")
                
                # Copy contents to src directory
                for item in template_dir.glob("*"):
                    if item.is_dir():
                        shutil.copytree(item, src_dir / item.name, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, src_dir)
                
                click.echo(f"Template files copied successfully to {src_dir}")
                
            except subprocess.CalledProcessError as e:
                click.echo(f"Error downloading template: {e}")
                click.echo(f"Output: {e.stdout.decode() if e.stdout else ''}")
                click.echo(f"Error: {e.stderr.decode() if e.stderr else ''}")
            except Exception as e:
                click.echo(f"Error setting up template: {e}")
            finally:
                # Return to original directory
                os.chdir(str(project_dir.parent))
        
    
    # Delete the UI folder if the user doesn't want it
    if not use_ui:
        ui_dir = project_dir / "ui"
        if ui_dir.exists():
            shutil.rmtree(ui_dir)
    
    # Create .env template file
    env_path = project_dir / ".env.example"
    with open(env_path, "w") as f:
        f.write("# API keys for external services\n")
        f.write("OPENAI_API_KEY=your-api-key-here\n")

    click.echo(f"Created .env.example: {env_path}")
    
    # Final instructions
    click.echo(f"\nProject {name} created successfully!")
    click.echo("Next steps:")
    click.echo(f"  1. cd {name}")
    click.echo("  2. Create a .env file with your API keys (see .env.example)")
    click.echo("  3. Deploy your workflow: llamactl deploy deployment.yml")
    
    if use_ui:
        click.echo("\nTo use the UI component:")
        click.echo("  1. Navigate to the UI directory: cd ui")
        click.echo("  2. Install dependencies (requires Node.js): npm install")
        click.echo("  3. Start the development server: npm run dev")


def write_yaml_with_comments(file_path: Path, config: Dict[str, Any]) -> None:
    """Write YAML with comments to help users understand configuration options."""
    # Add top-level comments
    header_comments = [
        "# Deployment configuration for llama-deploy",
        "#",
        "# This file defines your deployment setup including:",
        "# - Control plane configuration",
        "# - Message queue settings",
        "# - Services (workflows and UI components)",
        "#",
        "# For more information, see: https://github.com/run-llama/llama-deploy",
        "",
    ]
    
    # Convert dictionary to YAML
    yaml_content = yaml.safe_dump(config, sort_keys=False)
    
    # Add section comments
    section_comments = {
        "control-plane:": [
            "# Control plane configuration",
            "# The control plane manages the state of the system and coordinates services",
        ],
        "message-queue:": [
            "# Message queue configuration",
            "# The message queue handles communication between services",
        ],
        "default-service:": [
            "# The default service to use when no service is specified",
        ],
        "services:": [
            "# Service definitions",
            "# Each service represents a workflow or component in your system",
        ],
        "ui:": [
            "# UI component configuration",
            "# This defines the web interface for your deployment",
        ],
    }
    
    # Insert section comments into YAML content
    for section, comments in section_comments.items():
        if section in yaml_content:
            insertion_point = yaml_content.find(section)
            if insertion_point > 0:
                yaml_content = (
                    yaml_content[:insertion_point] + 
                    "\n" + "\n".join(comments) + "\n" + 
                    yaml_content[insertion_point:]
                )
    
    # Write to file with header comments
    with open(file_path, "w") as f:
        f.write("\n".join(header_comments) + "\n")
        f.write(yaml_content)

def create_deployment_config(name: str, port: int, message_queue_type: str, use_ui: bool = False) -> DeploymentConfig:
    """Create a deployment configuration using pydantic models."""
    # Create control plane config
    control_plane = ControlPlaneConfig(port=port)
    
    # Create message queue config
    message_queue_cls = SUPPORTED_MESSAGE_QUEUES.get(message_queue_type)
    if message_queue_cls is None:
        raise ValueError(f"Message queue type {message_queue_type} not supported")
    
    message_queue = message_queue_cls()
    
    # Create the example service
    service = Service(
        name="Example Workflow",
        source=ServiceSource(
            type=SourceType.local,
            location="src",
        ),
        import_path="src:workflow",
        python_dependencies=["llama-index-core>=0.12.0", "llama-index-llms-openai"],
        env={"OPENAI_API_KEY": "${OPENAI_API_KEY}"},
        env_files=["./.env"],
    )
    
    # Create UI service if requested
    ui_service = None
    if use_ui:
        ui_service = UIService(
            name="Example UI",
            source=ServiceSource(
                type=SourceType.local,
                location=".",
            ),
            import_path="ui",
            ts_dependencies={},
        )
    
    # Create the deployment config
    deployment_config = DeploymentConfig(
        name=name,
        control_plane=control_plane,
        message_queue=message_queue,
        default_service="example_workflow",
        services={"example_workflow": service},
        ui=ui_service,
    )
    
    return deployment_config
