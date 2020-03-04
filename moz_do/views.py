from flask import abort, Response

from moz_do import moz_do, models
#from moz_do import moz_do
from markupsafe import escape

from os import listdir, getcwd
from os.path import isfile, join

import json

STANDARD_HEADERS = {
    'Access-Control-Allow-Origin' : '*'
}

TYPES = {
    '.js':'text/javascript', '.json':'application/json','.html':'text/html'
}

@moz_do.route('/package/<pkgname>/<version>')
def show_package_by_name_and_version(pkgname, version):
    package_report = models.get_package_report(package = pkgname, version = version)
    if None != package_report:
        mimetype = "application/json"
        return Response(json.dumps(package_report.to_dict()), headers=STANDARD_HEADERS, mimetype=mimetype)
    else:
        #TODO: we probably want to return data to tell the user that a report is being generated
        abort(404)

@moz_do.route('/package/<pkgname>')
def show_package_by_name(pkgname):
    package_report = models.get_package_report(package = pkgname)
    if None != package_report:
        mimetype = "application/json"
        return Response(json.dumps(package_report.to_dict()), headers=STANDARD_HEADERS, mimetype=mimetype)
    else:
        #TODO: we probably want to return data to tell the user that a report is being generated
        abort(404)

@moz_do.route('/static/<filename>')
def serve_static_file(filename):
    # list the names of regular files that exist in the static dir
    static_dir = "static"
    files = [f for f in listdir(static_dir) if isfile(join(static_dir, f))]

    # if the requested filename exists in the list of regular filenames, serve it
    if filename in files:
        mimetype = "text/plain"

        # Cater for some common mimetypes
        dot_pos = filename.rfind('.')
        if -1 != dot_pos:
            mt = TYPES.get(filename[dot_pos:])
            if None != mt:
                mimetype = mt

        return Response(open(join(static_dir, filename), 'r').read(), headers=STANDARD_HEADERS, mimetype=mimetype)
    else:
        abort(404)

@moz_do.route('/__lbheartbeat__')
def lbheartbeat():
    return Response("badum badum", mimetype="text/plain")

@moz_do.route('/__heartbeat__')
def heartbeat():
    return Response("badum badum", mimetype="text/plain")

@moz_do.route('/__version__')
def version():
    # TODO - serve version.json from the filesystem
    version_info = dict(source = "https://github.com/mozilla-services/dependency-observatory",
                        version = "0.0.1",
                        commit = "",
                        build = ""
    )
    return Response(json.dumps(version_info), mimetype="application/json")