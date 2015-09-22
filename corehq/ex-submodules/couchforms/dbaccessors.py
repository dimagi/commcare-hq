from corehq.util.test_utils import unit_testing_only
from couchforms.const import DEVICE_LOG_XMLNS
from couchforms.models import XFormInstance, doc_types
from django.conf import settings


def get_form_ids_by_type(domain, type_, start=None, end=None):
    assert type_ in doc_types()
    startkey = [domain, type_]
    if end:
        endkey = startkey + end.isoformat()
    else:
        endkey = startkey + [{}]

    if start:
        startkey.append(start.isoformat())

    return [row['id'] for row in XFormInstance.get_db().view(
        "couchforms/all_submissions_by_domain",
        startkey=startkey,
        endkey=endkey,
        reduce=False,
    )]


def get_forms_by_type(domain, type_, recent_first=False,
                      limit=None):
    assert type_ in doc_types()
    # no production code should be pulling all forms in one go!
    assert limit is not None
    startkey = [domain, type_]
    endkey = startkey + [{}]
    if recent_first:
        startkey, endkey = endkey, startkey
    return XFormInstance.view(
        "couchforms/all_submissions_by_domain",
        startkey=startkey,
        endkey=endkey,
        reduce=False,
        descending=recent_first,
        include_docs=True,
        limit=limit,
        classes=doc_types(),
    ).all()


def get_forms_of_all_types(domain):
    assert settings.UNIT_TESTING
    startkey = [domain]
    endkey = startkey + [{}]
    return XFormInstance.view(
        "couchforms/all_submissions_by_domain",
        startkey=startkey,
        endkey=endkey,
        reduce=False,
        include_docs=True,
        classes=doc_types(),
    ).all()


def get_number_of_forms_by_type(domain, type_):
    assert type_ in doc_types()
    startkey = [domain, type_]
    endkey = startkey + [{}]
    submissions = XFormInstance.view(
        "couchforms/all_submissions_by_domain",
        startkey=startkey,
        endkey=endkey,
        reduce=True,
    ).one()
    return submissions['value'] if submissions else 0


def get_number_of_forms_of_all_types(domain):
    startkey = [domain]
    endkey = startkey + [{}]
    submissions = XFormInstance.view(
        "couchforms/all_submissions_by_domain",
        startkey=startkey,
        endkey=endkey,
        reduce=True,
    ).one()
    return submissions['value'] if submissions else 0


@unit_testing_only
def clear_forms_in_domain(domain):
    items = get_forms_of_all_types(domain)
    for item in items:
        item.delete()


def get_form_ids_for_user(domain, user_id):
    # todo: add pagination
    for result in XFormInstance.get_db().view(
            'reports_forms/all_forms',
            startkey=["submission user", domain, user_id],
            endkey=["submission user", domain, user_id, {}],
            reduce=False):
        yield result['id']


def get_number_of_forms_all_domains_in_couch():
    """
    Return number of non-error, non-log forms total across all domains
    specifically as stored in couch.

    (Can't rewrite to pull from ES or SQL; this function is used as a point
    of comparison between row counts in other stores.)

    """
    all_forms = (
        XFormInstance.get_db().view('couchforms/by_xmlns').one()
        or {'value': 0}
    )['value']
    device_logs = (
        XFormInstance.get_db().view('couchforms/by_xmlns',
                                    key=DEVICE_LOG_XMLNS).one()
        or {'value': 0}
    )['value']
    return all_forms - device_logs


def get_form_xml_element(form_id):
    return XFormInstance(_id=form_id).get_xml_element()
