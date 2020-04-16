from depobs.scanner.pipelines.crate_graph import pipeline as crate_graph
from depobs.scanner.pipelines.dep_graph import pipeline as dep_graph
from depobs.scanner.pipelines.fetch_package_data import pipeline as fetch_package_data
from depobs.scanner.pipelines.find_dep_files import pipeline as find_dep_files
from depobs.scanner.pipelines.find_git_refs import pipeline as find_git_refs
from depobs.scanner.pipelines.github_metadata import pipeline as github_metadata
from depobs.scanner.pipelines.postprocess import pipeline as postprocess
from depobs.scanner.pipelines.run_repo_tasks import pipeline as run_repo_tasks
from depobs.scanner.pipelines.rust_changelog import pipeline as rust_changelog
from depobs.scanner.pipelines.save_to_db import pipeline as save_to_db

pipelines = [
    crate_graph,
    dep_graph,
    fetch_package_data,
    find_dep_files,
    find_git_refs,
    github_metadata,
    postprocess,
    run_repo_tasks,
    rust_changelog,
    save_to_db,
]
