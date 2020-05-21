import os
import logging
import logging.config

import celery
from flask import Flask, request
from dockerflow.flask import Dockerflow
from dockerflow.logging import JsonLogFormatter

# enable mozlog request logging
from depobs.website.config import LOGGING

logging.config.dictConfig(LOGGING)
log = logging.getLogger(__name__)

# silence flask request logging
flasklog = logging.getLogger("werkzeug")
flasklog.setLevel(logging.ERROR)


# override the summary logger from the Dockerflow class to add
# logging of query string
# https://github.com/mozilla-services/python-dockerflow/issues/44
class Customflow(Dockerflow):
    def summary_extra(self):
        out = super().summary_extra()
        out["query_string"] = request.query_string.decode("utf-8")
        return out


def create_app(test_config=None):
    # reimport to pick up changes for testing and autoreload
    import depobs.database.models as models
    from depobs.website.scans import scans_blueprint
    from depobs.website.views import views_blueprint
    from depobs.website.score_details.blueprint import score_details_blueprint

    # create and configure the app
    app = Flask(__name__)  # do
    app.config.from_object("depobs.website.config")

    if test_config:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # setup up request-scoped DB connections
    log.info(f"connecting to database")
    models.db.init_app(app)
    models.migrate.init_app(app, models.db)

    dockerflow = Customflow(app, db=models.db)
    dockerflow.init_app(app)
    app.register_blueprint(scans_blueprint)
    app.register_blueprint(views_blueprint)
    app.register_blueprint(score_details_blueprint)

    return app


def create_celery_app(flask_app=None, test_config=None, tasks=None):
    """Returns a celery app that gives tasks access to a Flask
    application's context (e.g. the db variable).

    Uses the Flask app's config (e.g. when started in the web container)
    or creates a default Flask app (e.g. when started in the worker
    container).

    To avoid import cycles web views should use the
    depobs.website.get_celery_tasks to kick off celery tasks.
    """
    flask_app = flask_app if flask_app else create_app()
    if tasks is None:
        tasks = []

    celery_app = celery.Celery(
        flask_app.import_name,
        broker=flask_app.config["CELERY_BROKER_URL"],
        result_backend=flask_app.config["CELERY_RESULT_BACKEND"],
    )
    celery_app.conf.update(flask_app.config)
    celery_app.config_from_object(test_config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = ContextTask
    log.info(f"registering additional tasks: {tasks}")
    for task in tasks:
        celery_app.task(task)
    return celery_app


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))

    create_app().run(host=host, port=port)


if __name__ == "__main__":
    main()
