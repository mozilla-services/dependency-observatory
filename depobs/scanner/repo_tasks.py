from typing import (
    List,
    TypedDict,
)


class RunRepoTasksConfig(TypedDict):
    # Language to run commands for
    language: str

    # Package manager to run commands for
    package_manager: str

    # Run install, list_metadata, or audit tasks in the order
    # provided
    repo_tasks: List[str]

    # Docker image to run
    image_name: str
