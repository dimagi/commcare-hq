from __future__ import absolute_import
from collections import defaultdict, namedtuple
from datetime import datetime, date, time
import logging
import re
from lxml import etree
import os
from django.conf import settings
from corehq.apps.app_manager.util import all_apps_by_domain
from corehq.util.quickcache import quickcache
from couchforms.models import XFormDeprecated
from custom.openclinica.const import MODULE_EVENTS, FORM_QUESTION_ITEM, FORM_EVENTS, STUDY_APPS


class OpenClinicaIntegrationError(Exception):
    pass


Item = namedtuple('Item', ('study_event_oid', 'form_oid', 'item_group_oid', 'item_oid'))
AdminDataUser = namedtuple('AdminDataUser', ('user_id', 'first_name', 'last_name'))
OpenClinicaUser = namedtuple('OpenClinicaUser', ('user_id', 'first_name', 'last_name', 'username', 'full_name'))


# CDISC OMD XML namespace map
odm_nsmap = {
    'odm': "http://www.cdisc.org/ns/odm/v1.3",
    'OpenClinica': "http://www.openclinica.org/ns/odm_ext_v130/v3.1",
    'OpenClinicaRules': "http://www.openclinica.org/ns/rules/v3.1",
    'xsi': "http://www.w3.org/2001/XMLSchema-instance",
}


def quote_nan(value):
    """
    Returns value in single quotes if value is not a number

    >>> quote_nan('foo')
    "'foo'"
    >>> quote_nan('1')
    '1'

    """
    try:
        float(value)
        return value
    except ValueError:
        return "'{}'".format(value)


@quickcache(['domain'])
def get_question_items(domain):
    """
    Return a map of CommCare form questions to OpenClinica form items
    """

    def get_item_prefix(form_oid, ig_oid):
        """
        OpenClinica item OIDs are prefixed with "I_<prefix>_" where <prefix> is derived from the item's form
        OID. Dropping "I_<prefix>_" will give us the CommCare question name in upper case for human-built apps
        (i.e. the KEMRI app)

        >>> get_item_prefix('F_AE_AND_CONCO_7472_VERSION1', 'IG_AE_AN_AELOG_8290')
        'AE_AN'

        """
        form_name = form_oid[2:]  # Drop "F_"
        ig_name = ig_oid[3:]  # Drop "IG_"
        prefix = os.path.commonprefix((form_name, ig_name))
        if prefix.endswith('_'):
            prefix = prefix[:-1]
        return prefix

    def filter_items(items, module, form, question):
        """
        Filter a CommCare question's list of possible matching OpenClinica items, based on its module and form

        :param items: Candidate OpenClinica items
        :param module: The name of the CommCare question's module
        :param form: The XMLNS of the CommCare question's form
        :param question: The name of the question
        :return: an Item tuple
        :raise OpenClinicaIntegrationError: Unable to filter items
        """
        if not items:
            return None  # This is a CommCare-only question
        if len(items) == 1:
            return items[0]
        # Match module to event
        events = MODULE_EVENTS[module]
        if events is None:
            # CommCare-only module (e.g. subject registration)
            return None
        matches = [i for i in items if Item(*i).study_event_oid in events]
        if len(matches) == 1:
            return matches[0]
        # Match form to event
        events = FORM_EVENTS[form]
        matches = [i for i in items if Item(*i).study_event_oid in events]
        if len(matches) == 1:
            return matches[0]
        # Match form and question to an item
        try:
            return FORM_QUESTION_ITEM[(form, question)]
        except KeyError:
            raise OpenClinicaIntegrationError(
                'Unable to match CommCare question "{} > {} > {}" to an OpenClinica item. '
                'I got {}.'.format(module, form, question, [Item(*i).item_oid for i in items])
            )

    def read_question_item_map(odm, imported=True):
        """
        Return a dictionary of {question: [(study_event_oid, form_oid, item_group_oid, item_oid)]}

        Map CommCare questions to OpenClinica items, and append possible candidates to a list. That list will then
        be filtered based on the question's module and form in filter_items()

        :param odm: An ElementTree of the CISC ODM study metadata document
        :param imported: Whether the CommCare app was originally imported from the ODM doc. (Question names of
                         imported apps will match OpenClinica item OIDs exactly.)
        """
        # TODO: Post-KEMRI, remove `imported` parameter and code for when `imported` is False.
        # A dictionary of {question: [(study_event_oid, form_oid, item_group_oid, item_oid)]}
        question_item_map = defaultdict(list)

        meta_e = odm.xpath('./odm:Study/odm:MetaDataVersion', namespaces=odm_nsmap)[0]

        for se_ref in meta_e.xpath('./odm:Protocol/odm:StudyEventRef', namespaces=odm_nsmap):
            se_oid = se_ref.get('StudyEventOID')
            for form_ref in meta_e.xpath('./odm:StudyEventDef[@OID="{}"]/odm:FormRef'.format(se_oid),
                                         namespaces=odm_nsmap):
                form_oid = form_ref.get('FormOID')
                for ig_ref in meta_e.xpath('./odm:FormDef[@OID="{}"]/odm:ItemGroupRef'.format(form_oid),
                                           namespaces=odm_nsmap):
                    ig_oid = ig_ref.get('ItemGroupOID')
                    if not imported:
                        prefix = get_item_prefix(form_oid, ig_oid)
                        prefix_len = len(prefix) + 3  # len of "I_<prefix>_"
                    for item_ref in meta_e.xpath('./odm:ItemGroupDef[@OID="{}"]/odm:ItemRef'.format(ig_oid),
                                                 namespaces=odm_nsmap):
                        item_oid = item_ref.get('ItemOID')
                        if imported:
                            question = item_oid.lower()
                        else:
                            question = item_oid[prefix_len:].lower()  # Drop prefix
                            question = re.sub(r'^(.*?)_\d+$', r'\1', question)  # Drop OpenClinica-added ID
                        question_item_map[question].append((se_oid, form_oid, ig_oid, item_oid))
        return question_item_map

    def read_forms(question_item_map):
        """
        Return a dictionary that allows us to look up an OpenClinica item given a form XMLNS and question name
        """
        data = defaultdict(dict)
        openclinica_domains = (d for d, m in settings.DOMAIN_MODULE_MAP.iteritems() if m == 'custom.openclinica')
        for domain_ in openclinica_domains:
            for app in all_apps_by_domain(domain_):
                if app.name not in STUDY_APPS:
                    continue
                for ccmodule in app.get_modules():
                    for ccform in ccmodule.get_forms():
                        form = data[ccform.xmlns]
                        form['app'] = app.name
                        form['module'] = ccmodule.name['en']
                        form['name'] = ccform.name['en']
                        form['questions'] = {}
                        for question in ccform.get_questions(['en']):
                            name = question['value'].split('/')[-1]
                            # `question_item_map.get(name)` will return a list containing a single item in the
                            # case of imported apps, or list of possible items in the case of the KEMRI app.
                            # Determine which item this question maps to by filtering on module. A CommCare module
                            # maps (kinda) one-to-one to an OpenClinica event, and should narrow possible item
                            # matches to 1.
                            item = filter_items(question_item_map.get(name), form['module'], ccform.xmlns, name)
                            form['questions'][name] = item
        return data

    metadata_xml = get_study_metadata(domain)
    # The KEMRI app was not imported. Future apps will be.
    map_ = read_question_item_map(metadata_xml, imported=False)
    question_items = read_forms(map_)
    return question_items


def get_question_item(domain, form_xmlns, question):
    """
    Returns an Item namedtuple given a CommCare form and question name
    """
    question_items = get_question_items(domain)
    try:
        se_oid, form_oid, ig_oid, item_oid = question_items[form_xmlns]['questions'][question]
        return Item(se_oid, form_oid, ig_oid, item_oid)
    except KeyError:
        # Did an old form set the value of a question that no longer exists? Best to check that out.
        logging.error('Unknown CommCare question "{}" found in form "{}"'.format(question, form_xmlns))
        return None
    except TypeError:
        # CommCare question does not match an OpenClinica item. This is a CommCare-only question.
        return None


@quickcache(['domain'])
def get_study_metadata_string(domain):
    """
    Return the study metadata for the given domain as an XML string
    """
    from custom.openclinica.models import OpenClinicaSettings

    oc_settings = OpenClinicaSettings.for_domain(domain)
    if oc_settings.study.is_ws_enabled:
        raise NotImplementedError('Fetching study metadata using web services is not yet available')
    else:
        string = oc_settings.study.metadata
    # If the XML is Unicode but it says that it's UTF-8, then make it UTF-8.
    if isinstance(string, unicode):
        match = re.match(r'<\?xml .*?encoding="([\w-]+)".*?\?>', string)  # Assumes no whitespace up front
        if match:
            string = string.encode(match.group(1))
    return string


def get_study_metadata(domain):
    """
    Return the study metadata for the given domain as an ElementTree
    """
    # We can't cache an ElementTree instance. Split this function from get_study_metadata_string() to cache the
    # return value of get_study_metadata_string() when fetching via web service.
    return etree.fromstring(get_study_metadata_string(domain))


def get_study_constant(domain, name):
    """
    Return the study metadata of the given name for the given domain
    """
    xpath_text = lambda xml, xpath: xml.xpath(xpath, namespaces=odm_nsmap)[0].text
    xpath_xml = lambda xml, xpath: etree.tostring(xml.xpath(xpath, namespaces=odm_nsmap)[0])
    func = {
        'study_oid': lambda xml: xml.xpath('./odm:Study', namespaces=odm_nsmap)[0].get('OID'),
        'study_name': lambda xml: xpath_text(xml, './odm:Study/odm:GlobalVariables/odm:StudyName'),
        'study_description': lambda xml: xpath_text(xml, './odm:Study/odm:GlobalVariables/odm:StudyDescription'),
        'protocol_name': lambda xml: xpath_text(xml, './odm:Study/odm:GlobalVariables/odm:ProtocolName'),
        'study_xml': lambda xml: xpath_xml(xml, './odm:Study'),
        'admin_data_xml': lambda xml: xpath_xml(xml, './odm:AdminData'),
    }[name]
    metadata_xml = get_study_metadata(domain)
    return func(metadata_xml)


def get_item_measurement_unit(domain, item):
    """
    Return the measurement unit OID for the given Item, or None
    """
    xml = get_study_metadata(domain)
    mu_ref = xml.xpath(
        './odm:Study/odm:MetaDataVersion/odm:ItemDef[@OID="{}"]/odm:MeasurementUnitRef'.format(item.item_oid),
        namespaces=odm_nsmap)
    return mu_ref[0].get('MeasurementUnitOID') if mu_ref else None


def get_study_event_name(domain, oid):
    xml = get_study_metadata(domain)
    return xml.xpath('./odm:Study/odm:MetaDataVersion/odm:StudyEventDef[@OID="{}"]'.format(oid),
                     namespaces=odm_nsmap)[0].get('Name')


def is_study_event_repeating(domain, oid):
    xml = get_study_metadata(domain)
    return xml.xpath('./odm:Study/odm:MetaDataVersion/odm:StudyEventDef[@OID="{}"]'.format(oid),
                     namespaces=odm_nsmap)[0].get('Repeating') == 'Yes'


def is_item_group_repeating(domain, oid):
    xml = get_study_metadata(domain)
    return xml.xpath('./odm:Study/odm:MetaDataVersion/odm:ItemGroupDef[@OID="{}"]'.format(oid),
                     namespaces=odm_nsmap)[0].get('Repeating') == 'Yes'


def mk_oc_username(cc_username):
    """
    Makes a username that meets OpenClinica requirements from a CommCare username.

    Strips off "@domain.name", replaces non-alphanumerics, and pads with "_" if less than 5 characters

    >>> mk_oc_username('eric.idle@montypython.com')
    'eric_idle'
    >>> mk_oc_username('eric')
    'eric_'
    >>> mk_oc_username('I3#')
    'I3___'

    """
    username = cc_username.split('@')[0]
    username = re.sub(r'[^\w]', '_', username)
    if len(username) < 5:
        username += '_' * (5 - len(username))
    return username


@quickcache(['domain'])
def get_oc_users_by_name(domain):
    # We have to look up OpenClinica users by name because usernames are excluded from study metadata
    oc_users_by_name = {}
    xml = get_study_metadata(domain)
    admin = xml.xpath('./odm:AdminData', namespaces=odm_nsmap)[0]
    for user_e in admin:
        try:
            first_name = user_e.xpath('./odm:FirstName', namespaces=odm_nsmap)[0].text
        except IndexError:
            first_name = None
        try:
            last_name = user_e.xpath('./odm:LastName', namespaces=odm_nsmap)[0].text
        except IndexError:
            last_name = None
        user_id = user_e.get('OID')
        oc_users_by_name[(first_name, last_name)] = AdminDataUser(user_id, first_name, last_name)
    return oc_users_by_name


def get_oc_user(domain, cc_user):
    """
    Returns OpenClinica user details for corresponding CommCare user (CouchUser)
    """
    oc_users_by_name = get_oc_users_by_name(domain)
    oc_user = oc_users_by_name.get((cc_user.first_name, cc_user.last_name))
    return OpenClinicaUser(
        user_id=oc_user.user_id,
        username=mk_oc_username(cc_user.username),
        first_name=oc_user.first_name,
        last_name=oc_user.last_name,
        full_name=' '.join((oc_user.first_name, oc_user.last_name)),
    ) if oc_user else None


def oc_format_date(answer):
    """
    Format CommCare datetime answers for OpenClinica

    >>> from datetime import datetime
    >>> answer = datetime(2015, 8, 19, 19, 8, 15)
    >>> oc_format_date(answer)
    '2015-08-19 19:08:15'

    """
    if isinstance(answer, datetime):
        return answer.isoformat(sep=' ')
    if isinstance(answer, date) or isinstance(answer, time):
        return answer.isoformat()
    return answer


def originals_first(forms):
    """
    Return original (deprecated) forms before edited versions
    """
    def get_previous_versions(form_id):
        form_ = XFormDeprecated.get(form_id)
        if getattr(form_, 'deprecated_form_id', None):
            return get_previous_versions(form_.deprecated_form_id) + [form_]
        else:
            return [form_]

    for form in forms:
        if getattr(form, 'deprecated_form_id', None):
            for previous in get_previous_versions(form.deprecated_form_id):
                yield previous
        yield form
