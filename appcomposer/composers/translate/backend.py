import json
import urllib
from xml.dom import minidom
import StringIO

from babel import Locale, UnknownLocaleError
from flask import make_response, url_for

from appcomposer.appstorage.api import get_app
from appcomposer.composers.translate import translate_blueprint


"""
NOTE ABOUT THE GENERAL WORKFLOW DESIGN:
The current design for the export system is the following. Included here for reference purposes.
In the future it may be modified, as it has some issues / limitations.

NEW_APP()
 - GET OriginalSpec
 - GET OriginalXMLs
 - CREATE InternalJSONs

EDIT_APP()
 - GET OriginalSpec
 - GET OriginalXMLs
 - GET InternalJSONs
 - EDIT InternalJSONs
 - SAVE InternalJSONs

SERVE_APP()
 - GET OriginalSpec
 - GET InternalJSONs
 - SERVE OriginalBaseTranslation
 - SERVE JSONInternalTranslation


 NOTE ABOUT THE REQUIREMENTS ON THE APP TO BE TRANSLATED:
 The App to be translated should be already internationalized and should contain at least a reference to one Bundle,
 the Default language Bundle. This is a Locale node on the spec, with NO lang attribute and NO country attribute.
 (If this entry does not exist the App can't be translated).


 FILE NAMING CONVENTIONS:

 The convention we will try to use here is the following:

 Example: ca_ES_ALL.xml (for language files)

 ca would be the language.
 ES would be the country.
 ANY would be the group (the default).

 If any is not set, then it will be replaced with "all", in the right case. For instance,
 if lang is not specified it will be all_ES. Or if the country isn't, es_ALL.

 The default language is always all_ALL_ALL and should always be present.


 OTHER CONVENTIONS / GLOSSARY:

 "Bundle code" or "locale code" refers generally to the "es_ALL_ALL"-like string.

 """


class NoDefaultLanguageException(Exception):
    """
    Exception to be thrown when an App specified to be translated does not have a default translation.
    (And hence it is probably not ready to be translated).
    """

    def __init__(self, message=None):
        self.message = message


class ExternalFileRetrievalException(Exception):
    """
    Exception to be thrown when an operation failed because it was not possible to retrieve a file
    from an external host.
    """

    def __init__(self, message=None):
        self.message = message


class UnexpectedTranslateDataException(Exception):
    """
    Exception thrown when the format of the internally stored translate data does not seem
    to be as expected.
    """

    def __init__(self, message=None):
        self.message = message


class UnrecognizedLocaleCodeException(Exception):
    """
    Exception thrown when the format of a locale code does not seem to be
    as expected.
    """

    def __init__(self, message=None):
        self.message = message


class BundleExistsAlreadyException(Exception):
    """
    Exception thrown when an attempt to add a bundle to the manager exists but
    a bundle with that code exists already.
    """

    def __init__(self, message=None):
        self.message = message


class BundleManager(object):
    """
    To manage the set of bundles for an App, and to provide common functionality.
    """

    # TODO: Consider removing the original_gadget_spec, or adding different constructors for each use-case.
    def __init__(self, original_gadget_spec=None):
        """
        Builds the BundleManager.
        Note that there are additional CTORs available for specific use-cases, which start with create_*.
        @param original_gadget_spec: URL of the original XML of the App.
        """
        self._bundles = {}

        # Points to the original gadget spec XML.
        self.original_spec_file = original_gadget_spec

    @staticmethod
    def create_from_existing_app(app_data):
        """
        Acts as a CTOR. Creates a BundleManager for managing an App that exists already.

        @param app_data: JSON string, or JSON-able dictionary containing the Translate App's data.
        @return: The new BundleManager, with the specified App's data loaded.
        """
        if type(app_data) is str or type(app_data) is unicode:
            app_data = json.loads(app_data)

        spec_file = app_data["spec"]
        bm = BundleManager(spec_file)

        # TODO: Consider adding a load_from_jsonable.
        bm.load_from_json(json.dumps(app_data))

        return bm

    @staticmethod
    def get_locale_info_from_code(code):
        """
        Retrieves the lang, country and group from a full or partial locale code.
        @param code: Locale code. It can be a full code (ca_ES_ALL) or partial code (ca_ES).
        @return: (lang, country, group) or (lang, country), depending if it's full or partial.
        """
        splits = code.split("_")

        # If our code is only "ca_ES" style (doesn't include group).
        if len(splits) == 2:
            lang, country = splits
            return lang, country

        # If we have 3 splits then it is probably "ca_ES_ALL" style (includes group).
        elif len(splits) == 3:
            lang, country, group = splits
            return lang, country, group

        # Unknown number of splits. Throw an exception, it is not a recognized code.
        else:
            raise UnrecognizedLocaleCodeException("The locale code can't be recognized: " + code)

    @staticmethod
    def get_locale_english_name(lang, country):
        """
        Retrieves a string representation of a Locale.
        @param lang: Lang code.
        @param country: Country code.
        @return: String representation for the locale.
        """
        try:
            if country.upper() == 'ALL':
                country = ""
            return Locale(lang, country).english_name
        except UnknownLocaleError:
            return None

    @staticmethod
    def fullcode_to_partialcode(code):
        """
        Converts a full_code to a partial_code (with no group). That is, a code such as ca_ES_ALL to ca_ES.
        @param code: Fully fledged code, such as ca_ES_ALL.
        @return: Partial code, such as ca_ES.
        """
        lang, country, group = BundleManager.get_locale_info_from_code(code)
        return "%s_%s" % (lang.lower(), country.upper())

    @staticmethod
    def partialcode_to_fullcode(code, group):
        """
        Converts a partial_code to a full_code, adding group information. That is, a code such as ca_ES becomes
        a code such as ca_ES_ALL.
        @param code: Full code, such as ca_ES_ALL
        @return: Partial code, such as ca_ES.
        """
        lang, country = BundleManager.get_locale_info_from_code(code)
        return "%s_%s_%s" % (lang.lower(), country.upper(), group.upper())

    def get_locales_list(self):
        """
        get_locales_list()
        Retrieves a list containing dictionaries of the locales that are currently loaded in the manager.
        @return: List of dictionaries with the following information: {code, lang, country, group}
        """
        locales = []
        for key in self._bundles.keys():
            lang, country, group = key.split("_")
            loc = {"code": key, "pcode": BundleManager.fullcode_to_partialcode(key), "lang": lang, "country": country,
                   "group": group,
                   "repr": BundleManager.get_locale_english_name(lang, country)}
            locales.append(loc)
        return locales

    @staticmethod
    def _retrieve_url(url):
        """
        Simply retrieves a specified URL (Synchronously).
        @param url: URL to retrieve.
        @return: Contents of the URL.
        """
        handle = urllib.urlopen(url)
        contents = handle.read()
        return contents

    def load_full_spec(self, url):
        """
        Fully loads the specified Gadget Spec.
        This is meant to be used when first loading a new App, so that all existing languages are taken into account.
        Google default i18n mechanism doesn't support groups. Hence, all "imported" bundles will be created for the
        group "ALL", which is the default one for us.
        @param url:  URL to the XML Gadget Spec.
        @return: Nothing. The bundles are internally stored once parsed.
        """
        # Store the specified URL as the gadget spec.
        self.original_spec_file = url

        # Retrieve the original spec. This may take a while.
        xml_str = self._retrieve_url(url)

        # Extract the locales from the XML.
        locales = self._extract_locales_from_xml(xml_str)

        for lang, country, bundle_url in locales:
            bundle_xml = self._retrieve_url(bundle_url)
            bundle = Bundle.from_xml(bundle_xml, lang, country, "ALL")
            name = Bundle.get_standard_code_string(lang, country, "ALL")
            self._bundles[name] = bundle

    def to_json(self):
        """
        Exports everything to JSON. It includes both the JSON for the bundles, and a spec attribute, which
        links to the original XML file (it will be requested everytime).
        """
        data = {
            "spec": self.original_spec_file,
            "bundles": {}
        }
        for name, bundle in self._bundles.items():
            data["bundles"][name] = bundle.to_jsonable()
        return json.dumps(data)

    def load_from_json(self, json_str):
        """
        Loads the specified JSON into the BundleManager. It just loads from the JSON.
        It doesn't carry out any external request. Existing entries in the manager's bundles may be replaced.
        @param json_str: JSON string to load.
        @return: Nothing
        """
        appdata = json.loads(json_str)
        bundles = appdata["bundles"]
        for name, bundledata in bundles.items():
            # TODO: Inefficient. Consider refactoring this and providing the right methods so that it is not needed.
            # to constantly serialize/deserialize.
            bundlejs = json.dumps(bundledata)
            bundle = Bundle.from_json(bundlejs)
            self._bundles[name] = bundle
        return

    @staticmethod
    def _extract_locales_from_xml(xml_str):
        """
        _extract_locales_from_xml(xml_str)
        Extracts the Locale nodes info from an xml_str (a gadget spec).
        @param xml_str: String containing the XML of a locale file.
        @return: A list of tuples: (lang, country, message_file)
        @note: If the lang or country don't exist, it replaces them with "all" or "ALL" respectively.
        @note: The XML format is specified by Google and does not support the concept of "groups".
        """
        locales = []
        xmldoc = minidom.parseString(xml_str)
        itemlist = xmldoc.getElementsByTagName("Locale")
        for elem in itemlist:
            messages_file = elem.attributes["messages"].nodeValue

            try:
                lang = elem.attributes["lang"].nodeValue
            except KeyError:
                lang = "all"

            try:
                country = elem.attributes["country"].nodeValue
            except KeyError:
                country = "ALL"

            locales.append((lang, country, messages_file))
        return locales

    def _inject_locales_into_spec(self, appid, xml_str, respect_default=True):
        """
        _inject_locales_into_spec(appid, xml_str)

        Generates a new Gadget Spec from a provided Gadget Spec, replacing every original Locale with links
        to custom Locales, with application identifier appid.

        Optionally, it can avoid modifying the default translation.
        This is done so that if the original author updates the translation, this takes immediate effect
        into the translated versions of the App.

        @param appid: Application identifier of the current application. 
        @param xml_str: String containing the XML of the original Gadget Spec.

        @param respect_default: If false, every Locale will be removed and replaced with custom links to the
        language, using the appid as application identifier. If true, the same will be done to every Locale, EXCEPT the
        default language locale. The default language locale will be kept as-is.
        """

        xmldoc = minidom.parseString(xml_str)

        # Remove existing locales. Make sure we don't remove the default one (all_ALL) if we don't have to.
        locales = xmldoc.getElementsByTagName("Locale")
        default_locale_found = False
        for loc in locales:
            # Check whether it is the DEFAULT locale.
            if respect_default:
                # This is indeed the default node. Go on to next iteration without removing the locale.
                if "lang" not in loc.attributes.keys() and "country" not in loc.attributes.keys():
                    default_locale_found = True
                    continue

            # Remove the node.
            parent = loc.parentNode
            parent.removeChild(loc)

        # If we are supposed to respect the default, ensure that we actually found it.
        if respect_default:
            if not default_locale_found:
                raise NoDefaultLanguageException("The Gadget Spec does not seem to have a link to a default Locale."
                                                 "It is probably not ready to be translated.")

        # We have now removed the Locale nodes. Inject the new ones to the ModulePrefs node.
        module_prefs = xmldoc.getElementsByTagName("ModulePrefs")[0]
        for name, bundle in self._bundles.items():

            # Just in case we need to respect the default bundle.
            if respect_default:
                if name == "all_ALL_ALL":  # The default bundle MUST always be named thus.
                    # This is the default Locale. We have left the original one on the ModulePrefs node, so
                    # we don't need to append it. Go on to next Locale.
                    continue

            locale = xmldoc.createElement("Locale")

            # Build our locales to inject. We modify the case to respect the standard. It shouldn't be necessary
            # but we do it nonetheless just in case other classes fail to respect it.
            full_filename = url_for('.app_langfile', appid=appid,
                                    langfile=Bundle.get_standard_code_string(bundle.lang, bundle.country,
                                                                             bundle.group), _external=True)

            locale.setAttribute("messages", full_filename)
            if bundle.lang != "all":
                locale.setAttribute("lang", bundle.lang)
            if bundle.country != "ALL":
                locale.setAttribute("country", bundle.country)

            # Inject the node we have just created.
            locale.appendChild(xmldoc.createTextNode(""))
            module_prefs.appendChild(locale)

        return xmldoc.toprettyxml()

    def get_bundle(self, bundle_code):
        """
        get_bundle(bundle_code)

        Retrieves a bundle by its code.

        @param bundle_code: Name for the bundle. Example: ca_ES_ALL or all_ALL_ALL.
        @return: The bundle for the given name. None if the Bundle doesn't exist in the manager.
        """
        return self._bundles.get(bundle_code)

    def add_bundle(self, full_code, bundle):
        """
        Adds the specified Bundle to the BundleManager.
        @param full_code: Full code of the bundle, in ca_ES_ALL format (must include lang, country and group).
        @param bundle: The Bundle to add.
        @return: Nothing
        """
        if full_code in self._bundles:
            raise BundleExistsAlreadyException()
        self._bundles[full_code] = bundle

    def do_render_app_xml(self, appid):
        """
        Renders the Gadget Spec XML for the specified App.
        This method assumes that the BundleManager has already been loaded properly
        with the App's translations, and that the spec file is pointed to the right place.

        @param appid String with the unique ID of the application whose Bundles to generate. This is
        required because some URLs included in the generated XML include it.
        """
        xmlspec = self._retrieve_url(self.original_spec_file)
        output_xml = self._inject_locales_into_spec(appid, xmlspec, True)
        return output_xml


class Bundle(object):
    """
    Represents a Bundle. A bundle is a set of messages for a specific language, group and country.
    The default language, group and country is ANY.
    By convention, language is in lowercase while country is in uppercase.
    Group is uppercase too.
    """

    def __init__(self, lang, country, group="ALL"):
        self.country = country
        self.lang = lang
        self.group = group

        self._msgs = {
            # identifier : translation
        }

    @staticmethod
    def get_standard_code_string(lang, country, group):
        """
        From the lang, country and group information, it generates a standard name for the file.
        Standard names follow the convention: "ca_ES_ALL".
        Case is important.
        Also, if either of them is empty or None, then it will be replaced with "all" in the appropriate case.
        The XML file termination is NOT appended.
        """
        if lang is None or lang == "":
            lang = "all"
        if country is None or country == "":
            country = "ALL"
        if group is None or group == "":
            group = "ALL"
        return "%s_%s_%s" % (lang.lower(), country.upper(), group.upper())

    def get_msgs(self):
        """
        Retrieves the whole dictionary of translations for the Bundle.
        @return: Dictionary containing the translation. WARNING: Do not modify the dictionary.
        """
        return self._msgs

    def get_msg(self, identifier):
        """
        Retrieves the translation of a specific message.
        @param identifier: Identifier of the message to retrieve.
        @return: Message linked to the identifier, or None if it doesn't exist.
        """
        return self._msgs.get(identifier)

    def add_msg(self, word, translation):
        """
        Adds a translation to the dictionary.
        """
        self._msgs[word] = translation

    def remove_msg(self, word):
        """
        Removes a translation from the dictionary.
        """
        del self._msgs[word]

    def to_jsonable(self):
        """
        Converts the Bundle to a JSON-able dictionary.
        """
        bundle_data = {"country": self.country, "lang": self.lang, "group": self.group, "messages": self._msgs}
        return bundle_data

    def to_json(self):
        """
        Converts the Bundle to JSON.
        """
        bundle_data = {"country": self.country, "lang": self.lang, "group": self.group, "messages": self._msgs}
        json_str = json.dumps(bundle_data)
        return json_str

    @staticmethod
    def from_jsonable(bundle_data):
        """
        Builds a fully new Bundle from JSONable data. That is, a dictionary containing no references etc.
        """
        bundle = Bundle(bundle_data["lang"], bundle_data["country"], bundle_data["group"])
        bundle._msgs = bundle_data["messages"]
        return bundle

    @staticmethod
    def from_json(json_str):
        """
        Builds a fully new Bundle from JSON.
        """
        bundle_data = json.loads(json_str)
        return Bundle.from_jsonable(bundle_data)

    @staticmethod
    def from_xml(xml_str, lang, country, group="ALL"):
        """
        Creates a new Bundle from XML.
        """
        bundle = Bundle(lang, country, group)
        xmldoc = minidom.parseString(xml_str)
        itemlist = xmldoc.getElementsByTagName("msg")
        for elem in itemlist:
            bundle.add_msg(elem.attributes["name"].nodeValue, elem.firstChild.nodeValue.strip())
        return bundle

    def to_xml(self):
        """
        Converts the Bundle to XML.
        """
        out = StringIO.StringIO()
        out.write('<messagebundle>\n')
        for (name, msg) in self._msgs.items():
            out.write('    <msg name="%s">%s</msg>\n' % (name, msg))
        out.write('</messagebundle>\n')
        return out.getvalue()


@translate_blueprint.route('/app/<appid>/app.xml')
def app_xml(appid):
    """
    app_xml(appid)

    Provided for end-users. This is the function that provides hosting for the
    gadget specs for a specified App. The gadget specs are actually dynamically
    generated, as every time a request is made the original XML is obtained and
    modified.

    @param appid: Identifier of the App.
    @return: XML of the modified Gadget Spec with the Locales injected, or an HTTP error code
    if an error occurs.
    """
    app = get_app(appid)

    if app is None:
        return "Error 404: App doesn't exist", 404

    # The composer MUST be 'translate'
    if app.composer != "translate":
        return "Error 500: The composer for the specified App is not Translate", 500

    bm = BundleManager.create_from_existing_app(app.data)
    output_xml = bm.do_render_app_xml(appid)

    response = make_response(output_xml)
    response.mimetype = "application/xml"
    return response


@translate_blueprint.route('/app/<appid>/i18n/<langfile>.xml')
def app_langfile(appid, langfile):
    """
    app_langfile(appid, langfile, age)

    Provided for end-users. This is the function that provides hosting for the
    langfiles for a specified App. The langfiles are actually dynamically
    generated (the information is extracted from the Translate-specific information).

    @param appid: Appid of the App whose langfile to generate.
    @param langfile: Name of the langfile. Must follow the standard: ca_ES_ALL
    @return: Google OpenSocial compatible XML, or an HTTP error code
    if an error occurs.
    """
    app = get_app(appid)

    if app is None:
        return "Error 404: App doesn't exist", 404

    # The composer MUST be 'translate'
    if app.composer != "translate":
        return "Error 500: The composer for the specified App is not Translate", 500

    # Parse the appdata
    appdata = json.loads(app.data)

    bundles = appdata["bundles"]
    if langfile not in bundles:
        dbg_info = str(bundles.keys())
        return "Error 404: Could not find such language for the specified app. Available keys are: " + dbg_info, 404

    bundle = Bundle.from_jsonable(bundles[langfile])

    output_xml = bundle.to_xml()

    response = make_response(output_xml)
    response.mimetype = "application/xml"
    return response
