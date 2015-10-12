from __future__ import absolute_import
from collections import namedtuple
from datetime import datetime, date, time
import re
from lxml import etree
import os
from django.conf import settings
import yaml
from corehq.util.quickcache import quickcache
from couchforms.models import XFormDeprecated


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


def simplify(fancy):
    """
    Replace dict-like data types with dicts, and list-like data types with lists

    >>> from collections import defaultdict
    >>> simplify(defaultdict(list, {'bacon': ['spam']}))
    {'bacon': ['spam']}
    >>> simplify(('ham',))
    ['ham']
    >>> simplify({'spam'})
    ['spam']

    """
    if hasattr(fancy, 'keys'):
        return {simplify(k): simplify(fancy[k]) for k in fancy.keys()}
    elif isinstance(fancy, unicode):
        return fancy.encode('utf8')
    elif isinstance(fancy, str):
        return fancy
    elif hasattr(fancy, '__iter__'):
        return [simplify(i) for i in fancy]
    else:
        return fancy


@quickcache(['domain'])
def _get_question_items(domain):
    """
    Return a dictionary of form_xmlns: {question_name: openclinica_item}
    """
    file_path = os.path.join(settings.BASE_DIR, 'custom', 'openclinica', 'commcare_questions.yaml')
    with file(file_path) as question_items_file:
        question_items = yaml.load(question_items_file)
    return question_items


def get_question_item(domain, form_xmlns, question):
    """
    Returns an Item namedtuple given a CommCare form and question name
    """
    question_items = _get_question_items(domain)
    try:
        se_oid, form_oid, ig_oid, item_oid = question_items[form_xmlns]['questions'][question]
        return Item(se_oid, form_oid, ig_oid, item_oid)
    except KeyError:
        raise OpenClinicaIntegrationError('Unknown CommCare question "{}". Please run `./manage.py '
                                          'map_questions_to_openclinica`'.format(question))
    except TypeError:
        # CommCare question does not match an OpenClinica item. This happens with CommCare-only forms
        return None


@quickcache(['domain'])
def get_study_metadata(domain):
    """
    Return the study metadata for the given domain
    """
    # For this first OpenClinica integration project, for the sake of simplicity, we are just fetching
    # metadata from custom/openclinica/study_metadata.xml. In future, metadata must be stored for each domain.
    metadata_filename = os.path.join(settings.BASE_DIR, 'custom', 'openclinica', 'study_metadata.xml')
    return etree.parse(metadata_filename)


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
