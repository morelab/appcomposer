from flask import Flask
from flask import render_template, render_template_string
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(32)

#####
# Main components 
#####

from .user.user_application import initialize_user_component
from .admin import admin_blueprint

# User component
initialize_user_component(app)

# App Storage
from .appstorage import appstorage


app.register_blueprint(admin_blueprint,     url_prefix = '/admin')


#####
# Composers
#####

from .composers.translate import translate_blueprint
from .composers.adapt     import adapt_blueprint
from .composers.expert    import expert_blueprint

app.register_blueprint(translate_blueprint, url_prefix = '/composers/translate')
app.register_blueprint(adapt_blueprint,     url_prefix = '/composers/adapt')
app.register_blueprint(expert_blueprint,    url_prefix = '/composers/expert')


# Mostly for debugging purposes, this snippet will print the site-map so that we can check
# which methods we are routing.
@app.route("/site-map")
def site_map():
    lines = []
    for rule in app.url_map.iter_rules():
        line = str(escape(repr(rule)))
        lines.append(line)
        
    ret = "<br>".join(lines)
    return ret
