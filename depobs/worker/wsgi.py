from depobs.worker.main import app

# NB: set pyargv in uwsgi-worker.ini
app = app.cli.main()
