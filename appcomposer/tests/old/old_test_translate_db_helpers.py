import json
import unittest
import appcomposer
import appcomposer.application

from appcomposer.appstorage import api, add_var
from appcomposer.composers.translate.bundles import BundleManager, Bundle
from appcomposer.composers.translate.db_helpers import _db_declare_ownership, _db_get_lang_owner_app, _db_get_ownerships, \
    _db_get_proposals, _db_get_spec_apps, _db_transfer_ownership, _db_get_app_ownerships, _db_get_diff_specs, \
    save_bundles_to_db, load_appdata_from_db
from appcomposer.composers.translate.operations.ops_highlevel import find_unique_name_for_app
from appcomposer.login import current_user
import appcomposer.models
from appcomposer import db


class TestTranslateDbHelpers(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestTranslateDbHelpers, self).__init__(*args, **kwargs)
        self.flask_app = None
        self.tapp = None

    def login(self, username, password):
        return self.flask_app.post('/login', data=dict(
            login=username,
            password=password
        ), follow_redirects=True)

    def logout(self):
        return self.flask_app.get('/logout', follow_redirects=True)

    def _cleanup(self):
        """
        Does cleanup tasks in case the tests failed before.
        Can be invoked *before* and *after* the tests.
        """
        app = api.get_app_by_name("UTApp")
        if app is not None:
            api.delete_app(app)

        app = api.get_app_by_name("UTApp2")
        if app is not None:
            api.delete_app(app)

        app = api.get_app_by_name("UTApp (1)")
        if app is not None:
            api.delete_app(app)

    def setUp(self):
        appcomposer.app.config['DEBUG'] = True
        appcomposer.app.config['TESTING'] = True
        appcomposer.app.config['CSRF_ENABLED'] = False
        appcomposer.app.config["SECRET_KEY"] = 'secret'
        self.flask_app = appcomposer.app.test_client()
        self.flask_app.__enter__()

        rv = self.login("testuser", "password")

        # In case the test failed before, start from a clean state.
        self._cleanup()

        # Create an App for the tests.
        self.tapp = api.create_app("UTApp", "translate", "http://justatest.com", "{'spec':'http://justatest.com'}")

    def tearDown(self):
        self._cleanup()
        self.flask_app.__exit__(None, None, None)

    def test_current_user(self):
        cu = current_user()
        assert cu.login == "testuser"

    def test_declare_ownership(self):
        _db_declare_ownership(self.tapp, "test_TEST")

        vars = api.get_all_vars(self.tapp)
        var = next(var for var in vars if var.name == "ownership")
        assert var.name == "ownership"
        assert var.value == "test_TEST"

    def test_get_lang_owner_app(self):
        _db_declare_ownership(self.tapp, "test_TEST")
        owner_app = _db_get_lang_owner_app("http://justatest.com", "test_TEST")
        assert owner_app == self.tapp

    def test_get_ownerships(self):

        # There should be no ownerships declared on the spec.
        ownerships = _db_get_ownerships("http://justatest.com")
        assert len(ownerships) == 0

        # We now declare 1 ownership.
        _db_declare_ownership(self.tapp, "test_TEST")
        ownerships = _db_get_ownerships("http://justatest.com")
        assert len(ownerships) == 1

        # We now create a second app for further testing.
        app2 = api.create_app("UTApp2", "translate", "http://justatest.com", "{'spec':'http://justatest.com'}")

        # Ensure we still have 1 ownership.
        ownerships = _db_get_ownerships("http://justatest.com")
        assert len(ownerships) == 1

        # Add a second ownership for another language.
        _db_declare_ownership(app2, "testen_TESTEN")
        ownerships = _db_get_ownerships("http://justatest.com")
        assert len(ownerships) == 2

        # Ensure that the ownerships are right.
        firstOwnership = next(o for o in ownerships if o.value == "test_TEST")
        assert firstOwnership.app == self.tapp
        secondOwnership = next(o for o in ownerships if o.value == "testen_TESTEN")
        assert secondOwnership.app == app2

    def test_conflicting_composer(self):
        """
        Check that there is no mistake when there is a conflicting composer using the same appvar names.
        """
        # We now declare 1 ownership.
        _db_declare_ownership(self.tapp, "test_TEST")
        ownerships = _db_get_ownerships("http://justatest.com")
        assert len(ownerships) == 1

        # We now create a non-translate app.
        app2 = api.create_app("UTApp2", "dummy", "http://justatest.com", "{'spec':'http://justatest.com'}")
        api.add_var(app2, "ownership", "test_TEST")

        # Make sure that even though we added an ownership on an app with the same spec, it won't be
        # taken into account because it is a DUMMY and not a TRANSLATE composer.
        assert len(ownerships) == 1

    def test_conflicting_composer_proposal(self):
        """
        Check that there is no mistake when there is a conflicting composer using the same appvar names.
        """
        # We now declare add 1 proposal to the app.
        add_var(self.tapp, "proposal", "{}")

        # We now create a non-translate app.
        app2 = api.create_app("UTApp2", "dummy", "http://justatest.com", "{'spec':'http://justatest.com'}")
        # We add 1 proposal to the app with the same spec but different composer type.
        add_var(app2, "proposal", "{}")

        # Get the proposals for our app.
        proposals = _db_get_proposals(self.tapp)
        assert len(proposals) == 1


    def test_find_unique_name_for_app(self):
        # There is no conflict, so the name should be exactly the chosen one.
        name = find_unique_name_for_app("UTAPPDoesntExist")
        assert name == "UTAPPDoesntExist"

        # There is a conflict, so the name should include a number, starting at 1.
        name = find_unique_name_for_app("UTApp")
        assert name == "UTApp (1)"

        # We create a new app so that we can force a second conflict.
        app2 = api.create_app("UTApp (1)", "translate", "http://justatest.com", "{'spec':'http://justatest.com'}")
        name = find_unique_name_for_app("UTApp")
        assert name == "UTApp (2)"

    def test_get_proposals(self):

        proposals = _db_get_proposals(self.tapp)
        len(proposals) == 0

        # We add a fake proposal for the test app we have.
        # The data for the proposal is NOT valid, but shouldn't affect this test.
        api.add_var(self.tapp, "proposal", "{}")
        api.add_var(self.tapp, "proposal", "{}")
        proposals = _db_get_proposals(self.tapp)
        assert len(proposals) == 2

    def test_get_spec_apps(self):
        apps = _db_get_spec_apps("http://justatest.com")
        assert len(apps) == 1

        # Add a second spec (which should NOT be retrieved) for further testing.
        app2 = api.create_app("UTApp (1)", "translate", "http://different.com", "{'spec':'http://different.com'}")
        apps = _db_get_spec_apps("http://justatest.com")
        # Should still be 1. The new app is of a different spec.
        assert len(apps) == 1

        # Add a second spec (which should be retrieved) for further testing.
        app2 = api.create_app("UTApp2", "translate", "http://justatest.com", "{'spec':'http://justatest.com'}")
        apps = _db_get_spec_apps("http://justatest.com")
        # Should now be 2.
        assert len(apps) == 2

    def test_get_spec_apps_empty(self):
        """
        Calling test_get_spec_apps on a non-existing spec gets an empty list.
        :return:
        """
        apps = _db_get_spec_apps("http://doesnt-exist.com")
        assert len(apps) == 0

    def test_transfer_ownership(self):
        """
        Tests the method to transfer ownership.
        """
        # We now declare 1 ownership.
        _db_declare_ownership(self.tapp, "test_TEST")
        ownerships = _db_get_ownerships("http://justatest.com")
        assert len(ownerships) == 1
        # We now create a second app for further testing.
        app2 = api.create_app("UTApp2", "translate", "http://justatest.com", "{'spec':'http://justatest.com'}")

        # We transfer the ownership to the second app.
        _db_transfer_ownership("test_TEST", self.tapp, app2)

        # Verify that the ownership has indeed been transferred..
        owner = _db_get_lang_owner_app("http://justatest.com", "test_TEST")
        assert owner == app2

    def test_get_diff_specs(self):
        """
        Check that we can retrieve a list of all specs from the DB. Because we don't re-create
        a test DB explicitly, the checks are limited.
        """
        specs = _db_get_diff_specs()
        assert "http://justatest.com" in specs

        app2 = api.create_app("UTApp2", "translate", "ATESTSPEC", "{'spec':'ATESTSPEC'}")

        specs = _db_get_diff_specs()
        assert "http://justatest.com" in specs
        assert "ATESTSPEC" in specs

    def test_get_app_ownerships(self):
        """
        Test the method to retrieve the ownerships given an app.
        """
        _db_declare_ownership(self.tapp, "test_TEST")
        ownerships = _db_get_app_ownerships(self.tapp)
        assert len(ownerships) == 1

    def test_save_bundles_to_db(self):
        """
        Test the method to save a Bundle Manager of an App to the database, using
        the revamped DB.
        :return:
        """

        testBundle = Bundle("all", "ALL", "ALL")
        testBundle._msgs["key.one"] = "One"
        testBundle._msgs["key.two"] = "Two"

        bm = BundleManager()
        bm._bundles = {}
        bm._bundles["all_ALL_ALL"] = testBundle

        save_bundles_to_db(self.tapp, bm)

        # Retrieve the bundles from the DB.
        bundle = db.session.query(appcomposer.models.Bundle).filter_by(app=self.tapp, lang="all_ALL", target="ALL").first()
        assert bundle is not None

        self.assertIsNotNone(bundle)
        self.assertEquals("all_ALL", bundle.lang)
        self.assertEquals("ALL", bundle.target)

        messages = db.session.query(appcomposer.models.Message).filter_by(bundle=bundle).all()
        messages = {m.key: m.value for m in messages}

        self.assertEquals(2, len(messages))
        self.assertEquals("One", messages["key.one"])
        self.assertEquals("Two", messages["key.two"])

    def test_load_appdata_from_db(self):
        """
        Test the method to load the appdata as if it was the old legacy JSON object from the database.
        :return:
        """
        data = {
            "spec": "http://justatest.com",
            "random_setting": 1,
            "bundles": {
                "all_ALL_ALL": {
                    "lang": "all",
                    "country": "ALL",
                    "target": "ALL",
                    "messages" : {
                        "key.one": "One"
                    }
                }
            }
        }
        self.tapp.data = json.dumps(data)
        db.session.add(self.tapp)
        db.session.commit()

        appdata = load_appdata_from_db(self.tapp)

        # The bundles should now be empty, because load_appdata_from_db should not rely on the data's bundles, but
        # on the db information (and for now there is none). The settings should be respected.
        self.assertIsNotNone(appdata)
        self.assertIn("random_setting", appdata)
        self.assertIn("bundles", appdata)
        self.assertTrue(len(appdata["bundles"]) == 0)


        # To further test info retrieval, we need to add info to the db.
        testBundle = Bundle("all", "ALL", "ALL")
        testBundle._msgs["key.three"] = "Three"
        testBundle._msgs["key.four"] = "Four"
        bm = BundleManager()
        bm._bundles = {}
        bm._bundles["all_ALL_ALL"] = testBundle
        save_bundles_to_db(self.tapp, bm)


        appdata = load_appdata_from_db(self.tapp)
        self.assertTrue(appdata["bundles"]["all_ALL_ALL"]["messages"]["key.three"] == "Three")
        self.assertTrue(appdata["bundles"]["all_ALL_ALL"]["messages"]["key.four"] == "Four")


