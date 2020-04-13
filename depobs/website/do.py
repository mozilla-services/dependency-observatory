import os
import logging

from flask import Flask


log = logging.getLogger("do")
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)


def create_app(test_config=None):
    # reimport to pick up changes for testing and autoreload
    import depobs.website.models as models
    from depobs.website.scans import scans_blueprint
    from depobs.website.views import views_blueprint

    # create and configure the app
    app = Flask(__name__)  # do

    if os.environ.get("INIT_DB", False) == "1":
        log.info("Initializing DO DB")
        models.init_db()

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))

    app.config.update(SERVER_NAME=f"{host}:{port}",)

    if test_config:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    app.register_blueprint(scans_blueprint)
    app.register_blueprint(views_blueprint)
    return app


def main():
    create_app().run()


if __name__ == "__main__":
    main()
