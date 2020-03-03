from flask import Flask
import os
from moz_do import moz_do as app

if __name__ == '__main__':
    host = os.environ.get('HOST','0.0.0.0')
    port = int(os.environ.get('PORT','8000'))
    debug = bool(os.environ.get('DEBUG','False'))
    
    app.run(host=host,port=port,debug=debug)