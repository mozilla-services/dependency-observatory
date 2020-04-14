import os
import logging
import logging.config

from celery import Celery
from flask import Flask
from dockerflow.flask import Dockerflow
from dockerflow.logging import JsonLogFormatter

# enable mozlog request logging
from depobs.website.config import LOGGING

logging.config.dictConfig(LOGGING)
log = logging.getLogger(__name__)

# silence flask request logging
flasklog = logging.getLogger("werkzeug")
flasklog.setLevel(logging.ERROR)


def create_app(test_config=None):
    # reimport to pick up changes for testing and autoreload
    import depobs.website.models as models
    from depobs.website.scans import scans_blueprint
    from depobs.website.views import views_blueprint

    # create and configure the app
    app = Flask(__name__)  # do
    dockerflow = Dockerflow(app)
    dockerflow.init_app(app)

    app.config.update(
        SQLALCHEMY_DATABASE_URI=os.environ.get("SQLALCHEMY_DATABASE_URI", None),
        SQLALCHEMY_TRACK_MODIFICATIONS=bool(
            os.environ.get("SQLALCHEMY_TRACK_MODIFICATIONS", False)
        ),
        CELERY_BROKER_URL=os.environ.get("CELERY_BROKER_URL", None),
        CELERY_RESULT_BACKEND=os.environ.get("CELERY_RESULT_BACKEND", None),
    )

    if test_config:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # setup up request-scoped DB connections
    log.info(f"Initializing DO DB: {app.config['SQLALCHEMY_DATABASE_URI']}")
    models.db.init_app(app)
    if os.environ.get("INIT_DB", False) == "1":
        models.create_tables_and_views(app)

    app.register_blueprint(scans_blueprint)
    app.register_blueprint(views_blueprint)

    return app


def create_celery_app(flask_app=None):
    import depobs.worker.celeryconfig as celeryconfig

    flask_app = flask_app if flask_app else create_app()
    celery_app = Celery(
        flask_app.import_name,
        broker=flask_app.config["CELERY_BROKER_URL"],
        result_backend=flask_app.config["CELERY_RESULT_BACKEND"],
    )
    celery_app.config_from_object(celeryconfig)

    TaskBase = celery_app.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery_app.Task = ContextTask
    return celery_app


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))

    create_app().run(host=host, port=port)


if __name__ == "__main__":
    main()
