from flask import Flask
moz_do = Flask(__name__)

from depobs.website import views
