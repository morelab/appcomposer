from flask import redirect, request, flash, session, render_template_string, url_for
from flask.ext.admin import Admin, BaseView, AdminIndexView, expose
from flask.ext.wtf import TextField, Form, PasswordField, NumberRange, DateTimeField
from appcomposer.models import App
from .fields import DisabledTextField

from appcomposer import models
from appcomposer.login import current_user
from appcomposer.db import db_session

from sqlalchemy.orm import scoped_session, sessionmaker

# List of all available composers
from appcomposer.application import COMPOSERS


def initialize_user_component(app):
    # Initialize the Admin
    # URL describes through which address we access the page.
    # Endpoint enables us to do url_for('userp') to yield the URL
    url = '/user'
    admin = Admin(index_view=HomeView(url=url, endpoint='user'), name="User Profile", url=url, endpoint="home-user")
    admin.add_view(ProfileEditView(name="Profile", url='profile', endpoint='user.profile'))
    admin.add_view(AppsView(name="Apps", url="apps", endpoint='user.apps'))
    admin.init_app(app)


class UserBaseView(BaseView):
    """
    View that will probably be used as base for all other User views.
    It includes common functionality such as logged-in verification.
    """

    def is_accessible(self):
        self._current_user = current_user()
        return self._current_user is not None

    def _handle_view(self, *args, **kwargs):
        if not self.is_accessible():
            return redirect(url_for('login', next=request.url))

        return super(UserBaseView, self)._handle_view(*args, **kwargs)


class EditView(UserBaseView):
    """
    Edit View. The view used to view and edit common user information such as
    email, name, etc.
    """

    @expose('/')
    def index(self):
        return self.render("user/index.html")


class HomeView(UserBaseView):
    """
    Home View. Standard entry view which lets us choose a composer with which to create a new app.
    """

    @expose('/')
    def index(self):
        return self.render('user/index.html', composers=COMPOSERS)


class ProfileEditForm(Form):
    """
    The form used for the Profile Edit view.
    """
    name = DisabledTextField(u"Name:")
    login = DisabledTextField(u"Login:")
    email = TextField(u"E-mail:")
    password = PasswordField(u"Password:", description="Password.")
    organization = TextField(u"Organization:")
    role = TextField(u"Role:")
    creation_date = DisabledTextField(u"Creation date:")
    last_access_date = DisabledTextField(u"Last access:")
    auth_system = TextField(u"Auth system:")


class AppsView(UserBaseView):
    def __init__(self, *args, **kwargs):
        super(UserBaseView, self).__init__(*args, **kwargs)

    """
    Apps View. Will list all the apps owned by someone. He will be able to edit and delete them,
    and in the future will probably offer some additional options.
    """

    @expose('/')
    def index(self):
        # Retrieve the apps
        apps = db_session.query(App).filter_by(owner_id=self._current_user.id).all()
        return self.render('user/profile-apps.html', apps=apps)


class ProfileEditView(UserBaseView):
    # TODO: Make sure this method is necessary. Remove it otherwise, it's not very pretty.
    def __init__(self, *args, **kwargs):
        super(ProfileEditView, self).__init__(*args, **kwargs)

    @expose(methods=['GET', 'POST'])
    def index(self):
        """
        index(self)
        
        This method will be invoked for the Profile Edit view. This view is used for both viewing and updating
        the user profile. It exposes both GET and POST, for viewing and updating respectively.
        """

        # This will be passed as a template parameter to let us change the password.
        # (And display the appropriate form field).
        change_password = True

        user = current_user()
        if user is None:
            return (500, "User is None")


        # If it is a POST request to edit the form, then request.form will not be None
        # Otherwise we will simply load the form data from the DB
        if len(request.form):
            form = ProfileEditForm(request.form, csrf_enabled=True)
        else:
            # It was a GET request (just viewing). 
            form = ProfileEditForm(csrf_enabled=True)
            form.name.data = user.name
            form.login.data = user.login
            form.email.data = user.email
            form.organization.data = user.organization
            form.role.data = user.role
            form.creation_date.data = user.creation_date
            form.last_access_date.data = user.last_access_date
            form.auth_system.data = user.auth_system
            form.password.data = user.auth_data

        # If the method is POST we assume that we want to update and not just view
        # TODO: Make sure this is the proper way of handling that. The main purpose here
        # is to avoid carrying out a database commit if it isn't needed.
        if request.method == "POST" and form.validate_on_submit():
            # It was a POST request, the data (which has been modified) will be contained in
            # the request. For security reasons, we manually modify the user for these
            # settings which should actually be modifiable.
            user.email = form.email.data
            user.organization = form.organization.data
            user.role = form.role.data
            user.auth_type = form.auth_system.data # Probably in the release we shouldn't let users modify the auth this way
            user.auth_data = form.password.data # For the userpass method, the auth_data should contain the password. Eventually, should add hashing.
            db_session.add(user)
            db_session.commit()

        return self.render("user/profile-edit.html", form=form, change_password=change_password)
    
