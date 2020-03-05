import os
import logging

from flask import Flask

import moz_do.models
from moz_do import moz_do as app

log = logging.getLogger("do")
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)

if __name__ == '__main__':
    if os.environ.get('INIT_DB', False) == '1':
        log.info("Initializing DO DB")
        moz_do.models.init_db()

    host = os.environ.get('HOST','0.0.0.0')
    port = int(os.environ.get('PORT','8000'))
    debug = bool(os.environ.get('DEBUG','False'))

    app.run(host=host,port=port,debug=debug)
