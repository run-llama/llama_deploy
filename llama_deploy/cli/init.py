import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Type

import click
import yaml
from pydantic import BaseModel

# Import pydantic models
from llama_deploy.apiserver.deployment_config_parser import (
    DeploymentConfig,
    Service,
    ServiceSource,
    SourceType,
    UIService,
)


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
    "--template",
    type=click.Choice(["basic", "none"]),  # For future: add more templates
    default=None,
    help="Template to use for the workflow (currently only 'basic' is supported)",
)
def init(
    name: Optional[str] = None,
    destination: Optional[str] = None,
    template: Optional[str] = None,
) -> None:
    """Bootstrap a new llama-deploy project with a basic workflow and configuration."""

    # Interactive walkthrough - get inputs if not provided via CLI
    if name is None:
        name = click.prompt(
            "Project name",
            default="llama-deploy-app",
            show_default=True,
            type=str,
        )
        assert name

    if destination is None:
        destination = click.prompt(
            "Destination directory",
            default=".",
            type=str,
            show_default=True,
        )
        assert destination

    if template is None:
        click.echo("\nWorkflow template:")
        click.echo("  basic     - Basic workflow with OpenAI integration (recommended)")
        click.echo(
            "  none      - Do not create any sample workflow code (you just want a deployment.yml)"
        )

        template = click.prompt(
            "\nSelect workflow template",
            default="basic",
            type=click.Choice(["basic", "none"]),
            show_default=True,
        )

    # Additional configuration options
    if template != "none":
        use_ui = click.confirm(
            "\nWould you like to bundle a sample next.js UI with your deployment?",
            default=True,
        )
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

    # Create deployment.yml using pydantic models
    deployment_config = create_deployment_config(name, use_ui)
    deployment_path = project_dir / "deployment.yml"

    # Exclude several fields that would only confuse users
    deployment_dict = deployment_config.model_dump(
        mode="json",
        exclude_none=False,
        by_alias=True,
        exclude={  # type: ignore
            "control_plane": ["running", "internal_host", "internal_port"],
            "services": {"__all__": ["host", "port", "ts_dependencies"]},
            "ui": ["host", "port", "python_dependencies"],
        },
    )
    write_yaml_with_comments(deployment_path, deployment_dict, deployment_config)
    click.echo(f"Created deployment config: {deployment_path}")

    # Download the template from github
    if template != "none":
        repo_url = "https://github.com/run-llama/llama_deploy.git"
        template_path = f"templates/{template}"

        # Create a temporary directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            # Clone only the specific directory (with depth=1 for efficiency)
            click.echo("Cloning template files from repository...")

            try:
                # Clone the repository
                subprocess.run(
                    [
                        "git",
                        "clone",
                        "--depth=1",
                        "--filter=blob:none",
                        "--sparse",
                        repo_url,
                        temp_dir,
                    ],
                    check=True,
                )

                # Set up sparse checkout from the temp directory
                subprocess.run(
                    ["git", "sparse-checkout", "set", template_path],
                    check=True,
                    cwd=temp_dir,
                )

                # Copy template files to the project
                template_dir = Path(temp_dir) / template_path
                if not template_dir.exists():
                    raise FileNotFoundError(
                        f"Template directory not found: {template_dir}"
                    )

                # Copy contents to src directory (using absolute paths)
                for item in template_dir.glob("*"):
                    if "deployment.yml" in item.name:
                        # We don't want to copy the template deployment.yml file
                        # We generate our own deployment.yml file
                        continue

                    if item.is_dir():
                        shutil.copytree(
                            item, project_dir / item.name, dirs_exist_ok=True
                        )
                    else:
                        shutil.copy2(item, project_dir)

                click.echo(f"Template files copied successfully to {project_dir}")

            except subprocess.CalledProcessError as e:
                click.echo(f"Error downloading template: {e}")
                click.echo(f"Output: {e.stdout.decode() if e.stdout else ''}")
                click.echo(f"Error: {e.stderr.decode() if e.stderr else ''}")
            except Exception as e:
                click.echo(f"Error setting up template: {e}")

    # Delete the UI folder if the user doesn't want it
    if not use_ui:
        ui_dir = project_dir / "ui"
        if ui_dir.exists():
            shutil.rmtree(ui_dir)

    # Final instructions
    click.echo(f"\nProject {name} created successfully!")
    click.echo("Next steps:")
    click.echo(f"  1. cd {name}")
    click.echo(
        "  2. Edit the deployment.yml file to add your OpenAI API key and set other parameters"
    )
    click.echo("  3. Start the API server:")
    click.echo("     python -m llama_deploy.apiserver")
    click.echo(
        "     (or with Docker: docker run -p 4501:4501 -v .:/opt/app -w /opt/app llamaindex/llama-deploy)"
    )
    click.echo("  4. In another terminal, deploy your workflow:")
    click.echo("     llamactl deploy deployment.yml")
    click.echo("  5. Test your workflow:")
    click.echo(f"     llamactl run --deployment {name} --arg message 'Hello!'")

    if use_ui:
        click.echo("\nTo use the UI component:")
        click.echo(f"  • Open your browser to: http://localhost:4501/ui/{name}/")
        click.echo("  • The UI will be served automatically by the API server")


def write_yaml_with_comments(
    file_path: Path, config: Dict[str, Any], model: DeploymentConfig
) -> None:
    """Write YAML with comments based on pydantic model schemas and field descriptions."""

    def get_field_description(
        model_class: Type[BaseModel], field_name: str
    ) -> Optional[str]:
        """Get the description for a field from the model's JSON schema."""
        if not hasattr(model_class, "model_json_schema"):
            return None

        schema = model_class.model_json_schema()
        properties = schema.get("properties", {})
        field_schema = properties.get(field_name, {})
        return field_schema.get("description")

    def add_comments_to_yaml(
        yaml_content: str,
        model_class: Type[BaseModel],
        current_config: Dict[str, Any],
        indent_level: int = 0,
    ) -> str:
        """Recursively add inline comments to YAML content based on model schemas."""
        lines = yaml_content.split("\n")
        commented_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]

            # Skip empty lines and comments
            if not line.strip() or line.strip().startswith("#"):
                commented_lines.append(line)
                i += 1
                continue

            # Check if this line defines a field
            if ":" in line and not line.strip().startswith("-"):
                # Extract field name (convert YAML dashes to underscores for pydantic)
                yaml_field = line.split(":")[0].strip()
                pydantic_field = yaml_field.replace("-", "_")

                # Get description for this field
                description = get_field_description(model_class, pydantic_field)

                if description:
                    # Add inline comment to the field
                    if line.rstrip().endswith(":"):
                        # Field has no value on same line (nested object)
                        commented_line = line.rstrip() + f"  # {description}"
                    else:
                        # Field has value on same line
                        commented_line = line.rstrip() + f"  # {description}"
                    commented_lines.append(commented_line)
                else:
                    # No description, add line as-is
                    commented_lines.append(line)

                # Handle nested objects
                if pydantic_field in current_config and isinstance(
                    current_config[pydantic_field], dict
                ):
                    # Try to find the nested model class
                    if (
                        hasattr(model_class, "model_fields")
                        and pydantic_field in model_class.model_fields
                    ):
                        field_info = model_class.model_fields[pydantic_field]
                        nested_model_class = getattr(field_info, "annotation", None)

                        # Look ahead to capture the nested YAML content
                        nested_lines = []
                        j = i + 1
                        base_indent = len(line) - len(line.lstrip())

                        while j < len(lines):
                            next_line = lines[j]
                            if (
                                next_line.strip()
                                and len(next_line) - len(next_line.lstrip())
                                > base_indent
                            ):
                                nested_lines.append(next_line)
                                j += 1
                            elif (
                                next_line.strip()
                            ):  # Non-empty line at same or lower indent level
                                break
                            else:
                                nested_lines.append(next_line)
                                j += 1

                        # Process nested content if we have a model class
                        if nested_model_class and hasattr(
                            nested_model_class, "model_json_schema"
                        ):
                            nested_yaml = "\n".join(nested_lines)
                            processed_nested = add_comments_to_yaml(
                                nested_yaml,
                                nested_model_class,
                                current_config[pydantic_field],
                                indent_level + 1,
                            )
                            commented_lines.extend(
                                processed_nested.split("\n")[:-1]
                            )  # Remove last empty line
                            i = j - 1
                        else:
                            # Add nested lines without processing
                            commented_lines.extend(nested_lines)
                            i = j - 1
            else:
                commented_lines.append(line)

            i += 1

        return "\n".join(commented_lines)

    # Add header comments
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

    # Add field-specific comments based on schema
    commented_yaml = add_comments_to_yaml(yaml_content, type(model), config)

    # Add section comments
    section_comments = {
        "default_service:": [
            "# The default service to use when no service is specified",
        ],
        "services:": [
            "# Service definitions",
            "# Each service represents a workflow or component in your system",
        ],
        "ui:": [
            "# UI component configuration",
            "# This defines a web interface for your deployment",
        ],
    }

    # Insert section comments into YAML content
    for section, comments in section_comments.items():
        if section in commented_yaml:
            insertion_point = commented_yaml.find(section)
            if insertion_point > 0:
                commented_yaml = (
                    commented_yaml[:insertion_point]
                    + "\n"
                    + "\n".join(comments)
                    + "\n"
                    + commented_yaml[insertion_point:]
                )

    # Write to file with header comments
    with open(file_path, "w") as f:
        f.write("\n".join(header_comments) + "\n")
        f.write(commented_yaml)


def create_deployment_config(name: str, use_ui: bool = False) -> DeploymentConfig:
    """Create a deployment configuration using pydantic models."""
    # Create the example service
    service = Service(
        name="Example Workflow",
        source=ServiceSource(
            type=SourceType.local,
            location="src",
        ),
        import_path="src/workflow:workflow",
        python_dependencies=["llama-index-core>=0.12.37", "llama-index-llms-openai"],
        env={"OPENAI_API_KEY": "<your-openai-api-key-here>"},
        env_files=None,
        ts_dependencies=None,
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
            env_files=None,
            python_dependencies=None,
            env=None,
        )

    # Create the deployment config
    deployment_config = DeploymentConfig(
        name=name,
        default_service="example_workflow",
        services={"example_workflow": service},
        ui=ui_service,
    )

    return deployment_config
