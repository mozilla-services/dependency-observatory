from flask import Flask
app = Flask(__name__)  # depobs.website

from depobs.website import views
