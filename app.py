import os
import json
import urllib.parse
import pkgutil
import importlib
from pymonzo import MonzoAPI

from flask import Flask, request, redirect, url_for, render_template, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import exc

app = Flask(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:////tmp/flask_app.db')

CLIENT_ID_KEY = "clientId"
CLIENT_SECRET_KEY = "clientSecret"
CLIENT_TOKEN_KEY = "clientToken"
REDIRECT_URL_KEY = "RedirectUrl"
TOKEN_JSON_KEY = "tokenJSON"

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
db = SQLAlchemy(app)

class Config(db.Model):
    key = db.Column(db.String(32), primary_key=True)
    value = db.Column(db.String(1048))

    @staticmethod
    def insert_or_update(key, value):
        obj = Config.query.get(key)
        if obj:
            obj.value = value
            db.session.commit()
        else:
            db.session.add(Config(key=key, value=value))
            db.session.commit()

try:
    for x in db.session.query(Config):
        pass
except exc.ProgrammingError:
    db.create_all()


@app.route('/', methods=['GET'])
def index():
    return send_from_directory("static", "config.html")

@app.route('/submit_keys', methods=['POST'])
def submit_keys():
    Config.insert_or_update(CLIENT_ID_KEY, value=request.form['Client ID'])
    Config.insert_or_update(CLIENT_SECRET_KEY, value=request.form['Client Secret'])
    redirect_url = urllib.parse.urljoin(request.form['Heroku App URL'], "auth")
    Config.insert_or_update(REDIRECT_URL_KEY, value=redirect_url)
    return redirect("https://auth.getmondo.co.uk/?response_type=code&redirect_uri="+redirect_url+"&client_id="+request.form['Client ID'])

@app.route('/auth', methods=['GET'])
def auth():
    monzo = MonzoAPI(
        client_id=Config.query.get(CLIENT_ID_KEY).value,
        client_secret=Config.query.get(CLIENT_SECRET_KEY).value,
        redirect_url=Config.query.get(REDIRECT_URL_KEY).value,
        auth_code=request.args['code'],
        token_save_function=save_token_data
    )
    return "Success!"

@app.route('/webhook', methods=['POST'])
def webhook():
    monzo = get_monzo()

    for package in pkgutil.walk_packages('.'):
        if not package[2] and 'modules' in package[1]:
            module = importlib.import_module(package[1])
            if hasattr(module, 'webhook'):
                module.webhook(monzo, request.json)
    return "OK"

def save_token_data(monzo):
    token = monzo._token.copy()
    token.update(client_secret=monzo._client_secret)
    Config.insert_or_update(TOKEN_JSON_KEY, json.dumps(token))

def get_monzo():
    return MonzoAPI(
        token_data=json.loads(Config.query.get(TOKEN_JSON_KEY).value),
        token_save_function=save_token_data,
        redirect_url=Config.query.get(REDIRECT_URL_KEY).value
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
