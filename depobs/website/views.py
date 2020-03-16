from flask import abort, Response, request, send_from_directory
from werkzeug.exceptions import BadRequest

from depobs.website import models, app
from depobs.website.scans import tasks_api, validate_npm_package_version_query_params
from markupsafe import escape

from os import listdir, getcwd
from os.path import exists, isfile, join, dirname


STANDARD_HEADERS = {
    'Access-Control-Allow-Origin' : '*'
}

app.register_blueprint(tasks_api)


@app.errorhandler(BadRequest)
def handle_bad_request(e):
    return dict(description=e.description), 400


@app.route('/package', methods=["GET"])
def show_package_by_name_and_version_if_available():
    package_name, package_version, _ = validate_npm_package_version_query_params()

    package_report = models.get_package_report(package = package_name, version = package_version)
    if None != package_report:
        return package_report.json_with_dependencies()
    else:
        #TODO: we probably want to return data to tell the user that a report is being generated
        abort(404)


@app.route('/parents', methods=["GET"])
def get_parents_by_name_and_version():
    package_name, package_version, _ = validate_npm_package_version_query_params()

    package_report = models.get_package_report(package = package_name, version = package_version)
    if None != package_report:
        return package_report.json_with_parents()
    else:
        #TODO: we probably want to return data to tell the user that a report is being generated
        abort(404)


@app.after_request
def add_standard_headers_to_static_routes(response):
    response.headers.update(STANDARD_HEADERS)
    return response


@app.route('/__lbheartbeat__')
def lbheartbeat():
    return Response("badum badum", mimetype="text/plain")

@app.route('/__heartbeat__')
def heartbeat():
    return Response("badum badum", mimetype="text/plain")

@app.route('/__version__')
def version():
    return send_from_directory('/app', 'version.json')
