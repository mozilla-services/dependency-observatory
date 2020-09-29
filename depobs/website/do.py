import os
import logging
import logging.config

from flask import Flask, request
from dockerflow.flask import Dockerflow

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
    from depobs.website.views import views_blueprint

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

    dockerflow = Customflow(app, db=models.db, version_path="/app")
    dockerflow.init_app(app)
    app.register_blueprint(views_blueprint)

    return app


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))

    create_app().run(host=host, port=port)


if __name__ == "__main__":
    main()
