from base64 import b64decode
from collections import namedtuple
from datetime import datetime, date, time
import pytz
import re
import bz2
from time import strptime
from lxml import etree
from corehq.util.quickcache import quickcache
from couchforms.models import XFormDeprecated
import six


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

    >>> quote_nan('foo') if six.PY3 else quote_nan('foo').encode('utf-8')
    "'foo'"
    >>> quote_nan('1') if six.PY3 else quote_nan('1').encode('utf-8')
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
    Return a dictionary of {(event, question): (study_event_oid, form_oid, item_group_oid, item_oid)}
    """
    metadata_xml = get_study_metadata(domain)
    question_items = {}
    meta_e = metadata_xml.xpath('./odm:Study/odm:MetaDataVersion', namespaces=odm_nsmap)[0]
    for se_ref in meta_e.xpath('./odm:Protocol/odm:StudyEventRef', namespaces=odm_nsmap):
        se_oid = se_ref.get('StudyEventOID')
        for form_ref in meta_e.xpath('./odm:StudyEventDef[@OID="{}"]/odm:FormRef'.format(se_oid),
                                     namespaces=odm_nsmap):
            form_oid = form_ref.get('FormOID')
            for ig_ref in meta_e.xpath('./odm:FormDef[@OID="{}"]/odm:ItemGroupRef'.format(form_oid),
                                       namespaces=odm_nsmap):
                ig_oid = ig_ref.get('ItemGroupOID')
                for item_ref in meta_e.xpath('./odm:ItemGroupDef[@OID="{}"]/odm:ItemRef'.format(ig_oid),
                                             namespaces=odm_nsmap):
                    item_oid = item_ref.get('ItemOID')
                    event = se_oid.lower()
                    question = item_oid.lower()
                    question_items[(event, question)] = Item(se_oid, form_oid, ig_oid, item_oid)
    return question_items


def get_question_item(domain, event_id, question):
    """
    Returns an Item namedtuple given a CommCare form and question name
    """
    question_items = get_question_items(domain)
    try:
        se_oid, form_oid, ig_oid, item_oid = question_items[(event_id, question)]
        return Item(se_oid, form_oid, ig_oid, item_oid)
    except KeyError:
        # CommCare question does not match an OpenClinica item. This is a CommCare-only question.
        return None


@quickcache(['domain'])
def get_study_metadata_string(domain):
    """
    Return the study metadata for the given domain as a string

    Metadata is fetched from the OpenClinica web service
    """
    from custom.openclinica.models import OpenClinicaAPI, OpenClinicaSettings

    oc_settings = OpenClinicaSettings.for_domain(domain)
    if oc_settings.study.is_ws_enabled:
        password = bz2.decompress(b64decode(oc_settings.study.password))
        api = OpenClinicaAPI(
            oc_settings.study.url,
            oc_settings.study.username,
            password,
            oc_settings.study.protocol_id
        )
        string = api.get_study_metadata_string(oc_settings['STUDY'])
    else:
        string = oc_settings.study.metadata
    # If the XML is Unicode but it says that it's UTF-8, then make it UTF-8.
    if isinstance(string, six.text_type):
        match = re.match(r'<\?xml .*?encoding="([\w-]+)".*?\?>', string)  # Assumes no whitespace up front
        if match:
            string = string.encode(match.group(1))
    return string


def get_study_metadata(domain):
    """
    Return the study metadata for the given domain as an XML element
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

    >>> mk_oc_username('eric.idle@montypython.com') if six.PY3 else mk_oc_username('eric.idle@montypython.com').encode('utf-8')
    'eric_idle'
    >>> mk_oc_username('eric') if six.PY3 else mk_oc_username('eric').encode('utf-8')
    'eric_'
    >>> mk_oc_username('I3#') if six.PY3 else mk_oc_username('I3#').encode('utf-8')
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
        return answer.isoformat(sep=' ' if six.PY3 else b' ')
    if isinstance(answer, (date, time)):
        return answer.isoformat()
    return answer


def get_tz_mins(tz_str):
    """
    Return the timezone offset in minutes

    >>> get_tz_mins('Z')
    0
    >>> get_tz_mins('-05')
    -300
    >>> get_tz_mins('+0530')
    330

    """
    match = re.match(r'^(Z|(?P<sign>[+-])(?P<hours>\d{2}):?(?P<mins>\d{2})?)$', tz_str)
    if not match:
        raise ValueError('Unrecognized timezone offset')
    if tz_str == 'Z':
        return 0
    sign = 1 if match.group('sign') == '+' else -1
    hours = int(match.group('hours'))
    mins = int(match.group('mins') or 0)
    return sign * (hours * 60 + mins)


def oc_format_time(time_str, to_timezone, date_=None):
    """
    Format time strings for OpenClinica.

    >>> from pytz import timezone
    >>> oc_format_time('13:11:12.000Z', timezone('US/Eastern'))
    '08:11'
    >>> oc_format_time('15:11:12.000+02', timezone('US/Eastern'))
    '08:11'

    """
    match = re.match(r'^\d{2}:\d{2}:\d{2}.\d+([\+-]\d+|Z)$', time_str)
    if not match:
        return time_str
    tz_str = match.group(1)
    tz_offset = pytz.FixedOffset(get_tz_mins(tz_str))

    time_ = strptime(time_str, '%H:%M:%S.%f{}'.format(tz_str))
    if date_ is None:
        year, month, day = 2000, 1, 1
    else:
        year, month, day = date_.year, date_.month, date_.day
    datetime_ = datetime(
        year, month, day,
        time_.tm_hour, time_.tm_min, time_.tm_sec,
        tzinfo=tz_offset
    )
    as_timezone = datetime_.astimezone(to_timezone)
    return as_timezone.strftime('%H:%M')


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
