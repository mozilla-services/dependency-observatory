from depobs.worker.main import app

app = app.cli.main(
    args=[
        "run",
        "--task-name",
        "save_pubsub",
        "--task-name",
        "run_next_scan",
    ]
)
