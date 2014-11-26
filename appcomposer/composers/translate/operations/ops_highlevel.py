"""
Module for high-level translator operations.
"""
from collections import defaultdict
import json

from flask import flash

from appcomposer.appstorage.api import get_app_by_name, create_app, get_app
from appcomposer.babel import gettext
from appcomposer.composers.translate import CFG_SAME_NAME_LIMIT
from appcomposer.composers.translate.bundles import BundleManager
from appcomposer.composers.translate.db_helpers import save_bundles_to_db, _db_get_lang_owner_app, _db_declare_ownership, \
    load_appdata_from_db, _db_get_proposals
from appcomposer.composers.translate.operations.ops_exceptions import AppNotFoundException, InternalError
from appcomposer.composers.translate.operations.ops_lowlevel import do_languages_initial_merge
from appcomposer.composers.translate.updates_handling import on_leading_bundle_updated


def find_unique_name_for_app(base_name):
    """
    Generates a unique (for the current user) name for the app, using a base name.
    Because two apps for the same user cannot have the same name, if the base_name that the user chose
    exists already then we append (#num) to it. The number starts at 1.

    :param base_name: Name to use as base. If it's not unique (for the user) then we will append the counter.
    :return: The generated name, guaranteed to be unique for the current user, or None, if it was not possible
    to obtain the unique name. The failure would most likely be that the limit of apps with the same name has
    been reached. This limit is specified through the CFG_SAME_NAME_LIMIT variable.
    """
    if base_name is None:
        return None

    if get_app_by_name(base_name) is None:
        return base_name
    else:
        app_name_counter = 1
        while True:
            # Just in case, enforce a limit.
            if app_name_counter > CFG_SAME_NAME_LIMIT:
                return None
            composed_app_name = "%s (%d)" % (base_name, app_name_counter)
            if get_app_by_name(composed_app_name) is not None:
                app_name_counter += 1
            else:
                # Success. We found a unique name.
                return composed_app_name


def create_new_app(name, spec_url):
    """
    Creates a completely new application from the URL for a standard OpenSocial XML specification.
    This operation needs to request the external XML and in some cases external XMLs referred by it.
    As such, it can take a while ot complete, and there are potential security issues.

    :param name: Name to assign to the new Application. See find_unique_name_for_app.
    :type name: str
    :param spec_url: The URL to the OpenSocial XML specification file for the application.
    :type spec_url: str
    :return: (app, bm) tuple. App is the App DAO while bm is the BundleManager with the contents.
    :rtype: (App, BundleManager)
    """
    bm = BundleManager.create_new_app(spec_url)
    spec = bm.get_gadget_spec()

    # Build JSON data
    js = bm.to_json()
    # TODO: Remove this.
    # As an intermediate step towards db migration we remove the bundles from the app.data.
    # We cannot remove it from the bm to_json itself.
    jsdata = json.loads(js)
    if "bundles" in jsdata:
        del jsdata["bundles"]
    js = json.dumps(jsdata)

    # Create a new App from the specified XML
    app = create_app(name, "translate", spec_url, js)
    save_bundles_to_db(app, bm)

    # Handle Ownership-related logic here.
    # Locate the owner for the App's DEFAULT language.
    ownerApp = _db_get_lang_owner_app(spec_url, "all_ALL")
    # If there isn't already an owner for the default languages, we declare ourselves
    # as the owner for this App's default language.
    if ownerApp is None:
        _db_declare_ownership(app, "all_ALL")
        ownerApp = app

        # Report initial bundle creation. Needed for the MongoDB replica.
        for bundle in bm.get_bundles("all_ALL"):
            on_leading_bundle_updated(spec, bundle)

    # We do the same for the other included languages which are not owned already.
    # If the other languages have a translation but no owner, then we declare ourselves as their owner.
    for partialcode in bm.get_langs_list():
        otherOwner = _db_get_lang_owner_app(spec_url, partialcode)
        if otherOwner is None:
            _db_declare_ownership(app, partialcode)

            # Report initial bundle creation. Needed for the MongoDB replica.
            for bundle in bm.get_bundles(partialcode):
                on_leading_bundle_updated(spec, bundle)


    # Advanced merge. Merge owner languages into our bundles.
    do_languages_initial_merge(app, bm)

    return app, bm


def load_app(appid, targetlangs_list):
    """
    Loads an application from the database.

    TO-DO: Remove the targetlangs_list parameter, and somehow remove all the out-of-place returns.
    TO-DO: Fix docstring.

    :param appid: App uniqueid.
    :type appid: str
    :return: (app, bm) Returns a tuple with the app and the BundleManager with all the data.
    :rtype: (App, BundleManager)
    """
    app = get_app(appid)
    if app is None:
        raise AppNotFoundException()


    # Load a BundleManager from the app data.

    # Retrieve the app.data mostly from DB (new method) to stop relying on the legacy appdata.
    # TODO: Clear this up once the port is done.
    full_app_data = load_appdata_from_db(app)
    bm = BundleManager.create_from_existing_app(full_app_data)
    save_bundles_to_db(app, bm)

    spec = bm.get_gadget_spec()

    # Check whether an owner exists. If it doesn't, it means the original owner was deleted.
    # In that case, we make ourselves a new owner.
    # Locate the owner for the App's DEFAULT language.
    ownerApp = _db_get_lang_owner_app(spec, "all_ALL")
    # If there isn't already an owner for the default languages, we declare ourselves
    # as the owner for this App's default language.
    # TODO: NOTE: With the latest changes, this should never happen, because owners are declared
    # for all existing languages by the user who creates the app. It may, however, happen in the future,
    # when we take deletions and such into account.
    if ownerApp is None:
        _db_declare_ownership(app, "all_ALL")
        ownerApp = app

    translated_langs = bm.get_locales_list()

    if ownerApp == app:
        is_owner = True
    else:
        is_owner = False

    owner = ownerApp.owner

    if not is_owner and owner is None:
        # This should NEVER happen.
        flash(gettext("Error: Language Owner is None"), "error")
        raise InternalError("The app has no Language Owner")


    # Just for the count of proposals
    proposal_num = len(_db_get_proposals(app))

    # Build a dictionary. For each source lang, a list of source groups.
    src_groups_dict = defaultdict(list)
    for loc in translated_langs:
        src_groups_dict[loc["pcode"]].append(loc["group"])

    locales_codes = [tlang["pcode"] for tlang in translated_langs]

    # Remove from the suggested targetlangs those langs which are already present on the bundle manager,
    # because those will be added to the targetlangs by default.
    suggested_target_langs = [elem for elem in targetlangs_list if elem["pcode"] not in locales_codes]

    # We pass the autoaccept data var so that it can be rendered.
    # TODO: Optimize this once we have this fully covered with tests.
    data = json.loads(app.data)
    autoaccept = data.get("autoaccept",
                          True)  # We autoaccept by default. Problems may arise if this value changes, because it is used in a couple of places.


    return app, bm, owner, is_owner, proposal_num, src_groups_dict, suggested_target_langs, translated_langs, autoaccept




