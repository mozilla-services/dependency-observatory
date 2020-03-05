from flask import Flask
import os
import moz_do.models
from moz_do import moz_do as app

if __name__ == '__main__':
    if os.environ.get('INIT_DB', False) == '1':
        moz_do.models.init_db()

    host = os.environ.get('HOST','0.0.0.0')
    port = int(os.environ.get('PORT','8000'))
    debug = bool(os.environ.get('DEBUG','False'))

    app.run(host=host,port=port,debug=debug)
