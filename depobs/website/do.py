import os
import logging
import logging.config

from flask import Flask
from dockerflow.flask import Dockerflow
from dockerflow.logging import JsonLogFormatter

# enable mozlog request logging
from config import LOGGING

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)

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
        
    if test_config:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    if os.environ.get("INIT_DB", False) == "1":
        log.info("Initializing DO DB")
        models.init_db()

    app.register_blueprint(scans_blueprint)
    app.register_blueprint(views_blueprint)

    return app


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))

    create_app().run(host=host, port=port)


if __name__ == "__main__":
    main()
