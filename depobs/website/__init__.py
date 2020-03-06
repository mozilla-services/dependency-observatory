from flask import Flask
moz_do = Flask(__name__)

from moz_do.website import views
