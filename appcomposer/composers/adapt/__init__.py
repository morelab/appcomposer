import threading
from functools import wraps

from flask import Blueprint, flash, json, redirect, render_template, request, url_for
from flask_wtf import Form

from wtforms import TextField
from wtforms.validators import Required, Length

import appcomposer.appstorage.api as appstorage
from appcomposer.application import app

# Required imports for a customized app view for the adapt tool (a possible block to be refactored?)
from appcomposer.babel import lazy_gettext
from appcomposer.csrf import verify_csrf
from appcomposer.login import requires_login

info = {
    'blueprint': 'adapt',
    'url': '/composers/adapt',

    'new_endpoint': 'adapt.adapt_index',
    'edit_endpoint': 'adapt.adapt_edit',
    'create_endpoint': 'adapt.adapt_create',
    'duplicate_endpoint': 'adapt.adapt_duplicate',
    'delete_endpoint': 'dummy.delete',

    'name': lazy_gettext('Adaptor Composer'),
    'description': lazy_gettext('Adapt an existing app.')
}

adapt_blueprint = Blueprint(info['blueprint'], __name__)
adaptors_blueprints = []

ADAPTORS = {
    # 'identifier' : {
    #     'initial' : function,
    #     'adaptor' : adaptor_object,
    #     'name' : 'Something',
    #     'description' : 'Description', # Optional
    #     'about_endpoint' : 'Flask endpoint', # Optional
    # }
}


#
# Register the plug-ins. In the future we might have something more serious, relying on the
# extension system for flask.
#

_current_plugin = threading.local()

def load_plugins():
    # These plug-ins have been deprecated in favor of jsconfig
    # plugins = ['concept_mapper', 'hypothesis', 'edt', 'jsconfig']
    plugins = ['jsconfig']

    for plugin in app.config.get('ADAPT_PLUGINS', []):
        if plugin not in plugins:
            plugins.append(plugin)

    for plugin in plugins:
        _current_plugin.name = plugin
        try:
            __import__('appcomposer.composers.adapt.ext.%s' % plugin)
        finally:
            _current_plugin.name = None

class AdaptorPlugin(object):
    """ An AdaptorPlugin is an object generated by the adaptor and consumed 
    each plug-in. It contains the Flask blueprint as well as some useful 
    information (name, initial structure, etc.)."""
    def __init__(self, name, blueprint, initial = None, description = None, about_endpoint = None):
        self.name      = name
        self.blueprint = blueprint
        if initial is None:
            self.initial = {}
        else:
            self.initial   = initial
        self.description = description
        self._edit_endpoint = None
        self._data = None
        self.about_endpoint = about_endpoint

    def route(self, *args, **kwargs):
        return self.blueprint.route(*args, **kwargs)

    def get_name(self, appid):
        app = appstorage.get_app(appid)
        return app.name

    def load_data(self, appid):
        """ Wrapper of the appstorage API. It returns a valid JSON file. """
        app = appstorage.get_app(appid)
        return json.loads(app.data)

    def save_data(self, app_id, data):
        """ Wrapper of the appstorage API. It saves the data in JSON format. """
        app = appstorage.get_app(app_id)
        appstorage.update_app_data(app, data)

    def edit_route(self, func):
        """ Generates a route that already controls that the App ID exists

        @adaptor.edit_route
        def edit(app_id):
            # Whatever flask code
            # You may refer to this method as url_for('.edit')
            return "something"
        """
        self._edit_endpoint = '%s.%s' % (self.name, func.__name__)

        @self.blueprint.route("/edit/<appid>/", methods = ['GET', 'POST'])
        @requires_login
        @wraps(func)
        def wrapper(appid):
            # TODO: Improve this: do not load the whole thing. We just need the ID and so on.
            if not appid:
                return "appid not provided", 400
            app = appstorage.get_app(appid)
            if app is None:
                return "App not found", 500

            data = json.loads(app.data)
            adaptor_type = data["adaptor_type"]

            if adaptor_type != self.name:
                return "This Adaptor is not of this adaptor type", 400

            return func(appid)
        return wrapper

def create_adaptor(full_name, initial = {}, description = None, about_endpoint = None):
    # Make sure that:
    # 1. It's serializable to JSON (as it's gonna be later in the appstorage layer)
    # 2. It's never modified by any function
    initial = json.loads(json.dumps(initial))

    plugin = getattr(_current_plugin, 'name', None)
    if not plugin:
        raise Exception("The plug-in should not be loaded directly. It should be loaded by the load_plugins() method in the beginning")

    for blueprint in adaptors_blueprints:
        if blueprint.name == plugin:
            raise Exception("The plug-in %s is already registered. Don't call the method twice and check that the plug-in name is not in collision with other plug-in.")
        
    import_name = 'golab_adapt_%s' % plugin
    url_prefix = '/composers/adapt/adaptors/%s' % plugin

    plugin_blueprint = Blueprint(plugin, import_name, url_prefix = url_prefix, template_folder = 'templates', static_folder='static')

    adaptors_blueprints.append(plugin_blueprint)
    adaptor = AdaptorPlugin(plugin, plugin_blueprint, initial, description = description, about_endpoint = about_endpoint)

    if plugin in ADAPTORS:
        raise Exception("Plug-in id already registered: %s" % plugin)

    ADAPTORS[plugin] = {
        'name'    : full_name,
        'adaptor' : adaptor,
        'initial' : initial,
        'about_endpoint' : about_endpoint,
        'description' : description,
    }

    return adaptor


# 
# Common code 
# 


@adapt_blueprint.route("/", methods=["GET", "POST"])
@requires_login
def adapt_index():
    """
    adapt_index()
    Loads the main page with the selection of adaptor apps (concept map, hypothesis or experiment design).
    @return: The adaptor type that the user has selected.
    """
    if request.method == "POST":

        # Protect against CSRF attacks.
        if not verify_csrf(request):
            return render_template("composers/errors.html",
                                   message="Request does not seem to come from the right source (csrf check)"), 400

        adaptor_type = request.form["adaptor_type"]

        if adaptor_type and adaptor_type in ADAPTORS:
            # In order to show the list of apps we redirect to other url
            return redirect(url_for("adapt.adapt_create", adaptor_type = adaptor_type))
        else:
            # An adaptor_type is required.
            flash("Invalid adaptor type", "error")
    return render_template("composers/adapt/index.html", adaptors = ADAPTORS)

@adapt_blueprint.route("/create/<adaptor_type>/", methods=["GET", "POST"])
@requires_login
def adapt_create(adaptor_type):
    """
    adapt_create()
    Loads the form for creating new adaptor apps and the list of adaptor apps from a specific type.
    @return: The app unique id.
    """
    def build_edit_link(app):
        return url_for("adapt.adapt_edit", appid=app.unique_id)


    if adaptor_type not in ADAPTORS:
        flash("Invalid adaptor type", "error")
        return render_template('composers/adapt/create.html', apps=[], adaptor_type = adaptor_type, build_edit_link=build_edit_link)

    app_plugin = ADAPTORS[adaptor_type]

    apps = appstorage.get_my_apps(adaptor_type = adaptor_type)

    # If a get request is received, we just show the new app form and the list of adaptor apps
    if request.method == "GET":
        return render_template('composers/adapt/create.html', apps=apps, adaptor_type = adaptor_type, build_edit_link=build_edit_link)


    # If a post is received, we are creating an adaptor app.
    elif request.method == "POST":

        # Protect against CSRF attacks.
        if not verify_csrf(request):
            return render_template("composers/errors.html", message="Request does not seem to come from the right source (csrf check)"), 400

        # We read the app details provided by the user
        name = request.form["app_name"]
        app_description = request.form["app_description"]

        if not name:
            flash("An application name is required", "error")
            return render_template("composers/adapt/create.html", name=name, apps = apps, adaptor_type = adaptor_type, build_edit_link=build_edit_link)

        if not app_description:
            app_description = "No description"

        # Build the basic JSON schema of the adaptor app
        data = {
            'adaptor_version': '1',
            'name': unicode(name),
            'description': unicode(app_description),
            'adaptor_type': unicode(adaptor_type)
        }

        # Fill with the initial structure
        data.update(app_plugin['initial'])

        #Dump the contents of the previous block and check if an app with the same name exists.
        # (TODO): do we force different names even if the apps belong to another adaptor type?
        app_data = json.dumps(data)

        try:
            app = appstorage.create_app(name, 'adapt', app_data, description = app_description)
            appstorage.add_var(app, 'adaptor_type', unicode(adaptor_type))
        except appstorage.AppExistsException:
            flash("An App with that name already exists", "error")
            return render_template("composers/adapt/create.html", name=name, apps = apps, adaptor_type = adaptor_type, build_edit_link=build_edit_link)

        return redirect(url_for("adapt.adapt_edit", appid = app.unique_id))

class DuplicationForm(Form):
    name = TextField(lazy_gettext('Name'), validators = [ Required(), Length(min=4) ]) 

@adapt_blueprint.route("/duplicate/<appid>/", methods = ['GET', 'POST'])
@requires_login
def adapt_duplicate(appid):
    app = appstorage.get_app(appid)
    if app is None:
        return render_template("composers/errors.html", message = "Application not found")

    form = DuplicationForm()
    
    if form.validate_on_submit():

        # Protect against CSRF attacks.
        if not verify_csrf(request):
            return render_template("composers/errors.html",
                                   message="Request does not seem to come from the right source (csrf check)"), 400

        existing_app = appstorage.get_app_by_name(form.name.data)
        if existing_app:
            if not form.name.errors:
                form.name.errors = []
            form.name.errors.append(lazy_gettext("You already have an application with this name"))
        else:
            new_app = appstorage.create_app(form.name.data, 'adapt', app.data)
            for appvar in app.appvars:
                appstorage.add_var(new_app, appvar.name, appvar.value)

            return redirect(url_for('.adapt_edit', appid = new_app.unique_id))

    if not form.name.data:
        counter = 2
        potential_name = ''
        while counter < 1000:
            potential_name = '%s (%s)' % (app.name, counter)

            existing_app = appstorage.get_app_by_name(potential_name)
            if not existing_app:
                break
            counter += 1

        form.name.data = potential_name

    return render_template("composers/adapt/duplicate.html", form = form, app = app)

@adapt_blueprint.route("/edit/<appid>/", methods = ['GET', 'POST'])
@requires_login
def adapt_edit(appid):
    """
    adapt_edit()
    Form-based user interface for editing the contents of an adaptor app.
    @return: The final app with all its fields stored in the database.
    """
    if not appid:
        return "appid not provided", 400

    # TODO: Improve this: do not load the whole thing. We just need the variables.
    app = appstorage.get_app(appid)
    if app is None:
        return "Error: App not found", 500

    adaptor_types = [ var for var in app.appvars if var.name == 'adaptor_type' ]
    if not adaptor_types:
        return "Error: no attached adaptor_type variable"
    adaptor_type = adaptor_types[0].value

    if adaptor_type not in ADAPTORS:
        return "Error: adaptor %s not currently supported" % adaptor_type
    
    adaptor_plugin = ADAPTORS[adaptor_type]['adaptor']

    return redirect(url_for(adaptor_plugin._edit_endpoint, appid = appid))

## Tests

@adapt_blueprint.route("/more/<uuid_test>/", methods = ['GET', 'POST'])
def adapt_uuid(uuid_test):
    return uuid_test

"""
@app.errorhandler(404)
def not_found(error):
    return render_template('error.html'), 404
"""
