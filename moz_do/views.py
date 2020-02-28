from flask import abort, Response

from moz_do import moz_do
from markupsafe import escape

from os import listdir, getcwd
from os.path import isfile, join

TYPES = {
    '.js':'text/javascript', '.json':'application/json','.html':'text/html'
}

@moz_do.route('/package/<pkgname>')
def show_user_profile(pkgname):
    # show the package data for that package
    return 'Package %s' % escape(pkgname)

@moz_do.route('/static/<filename>')
def serve_static_file(filename):
    # list the names of regular files that exist in the static dir
    print(getcwd())
    static_dir = "static"
    files = [f for f in listdir(static_dir) if isfile(join(static_dir, f))]

    # if the requested filename exists in the list of regular filenames, serve it
    if filename in files:
        mimetype = "test/plain"

        # Cater for some common mimetypes
        dot_pos = filename.rfind('.')
        if -1 != dot_pos:
            mt = TYPES.get(filename[dot_pos:])
            if None != mt:
                mimetype = mt

        return Response(open(join(static_dir, filename), 'r').read(), mimetype=mimetype)
    else:
        abort(404)