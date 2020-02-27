from moz_do import moz_do
from markupsafe import escape

@moz_do.route('/package/<pkgname>')
def show_user_profile(pkgname):
    # show the package data for that package
    return 'Package %s' % escape(pkgname)