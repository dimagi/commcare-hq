from couchforms.models import XFormInstance, doc_types
from django.conf import settings


def get_form_ids_by_type(domain, type_, start=None, end=None):
    assert type_ in doc_types()
    startkey = [domain, 'by_type', type_]
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
    assert type_ in doc_types() or not type_
    if type_:
        startkey = [domain, 'by_type', type_]
    else:
        startkey = [domain, 'by_type']
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
    return get_forms_by_type(domain, None)


def get_number_of_forms_by_type(domain, type_):
    assert type_ in doc_types() or not type_
    if type_:
        startkey = [domain, 'by_type', type_]
    else:
        startkey = [domain, 'by_type']
    endkey = startkey + [{}]

    return XFormError.view(
        "couchforms/all_submissions_by_domain",
        startkey=startkey,
        endkey=endkey,
        reduce=True,
    ).one()['value']


def get_number_of_forms_of_all_types(domain):
    return get_number_of_forms_by_type(domain, None)


def get_forms_in_date_range(domain, start, end):
    XFormInstance.view(
        "couchforms/all_submissions_by_domain",
        startkey=[domain, "by_date", start.isoformat()],
        endkey=[domain, "by_date", end.isoformat(), {}],
        include_docs=True,
        reduce=False
    ).all()
