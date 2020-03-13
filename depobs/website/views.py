from flask import abort, Response, request, send_from_directory

from depobs.website import models, app
from depobs.website.scans import tasks_api
from markupsafe import escape

from os import listdir, getcwd
from os.path import exists, isfile, join, dirname

import json

STANDARD_HEADERS = {
    'Access-Control-Allow-Origin' : '*'
}

app.register_blueprint(tasks_api)


@app.route('/package/<pkgname>/<version>')
def show_package_by_name_and_version(pkgname, version):
    package_report = models.get_package_report(package = pkgname, version = version)
    if None != package_report:
        mimetype = "application/json"
        return Response(json.dumps(package_report.json_with_dependencies()), headers=STANDARD_HEADERS, mimetype=mimetype)
    else:
        #TODO: we probably want to return data to tell the user that a report is being generated
        abort(404)

@app.route('/package/<pkgname>')
def show_package_by_name(pkgname):
    package_report = models.get_package_report(package = pkgname)
    if None != package_report:
        mimetype = "application/json"
        return Response(json.dumps(package_report.json_with_dependencies()), headers=STANDARD_HEADERS, mimetype=mimetype)
    else:
        #TODO: we probably want to return data to tell the user that a report is being generated
        abort(404)

@app.route('/parents/<pkgname>/<version>')
def get_parents_by_name_and_version(pkgname, version):
    package_report = models.get_package_report(package = pkgname, version = version)
    if None != package_report:
        mimetype = "application/json"
        return Response(json.dumps(package_report.json_with_parents()), headers=STANDARD_HEADERS, mimetype=mimetype)
    else:
        #TODO: we probably want to return data to tell the user that a report is being generated
        abort(404)


@app.after_request
def add_standard_headers_to_static_routes(response):
    if request.path.startswith('/static'):
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
