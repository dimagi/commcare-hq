from couchforms.exceptions import ViewTooLarge
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
    assert type_ in doc_types()
    # no production code should be pulling all forms in one go!
    assert limit is not None
    startkey = [domain, 'by_type', type_]
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
    startkey = [domain, 'by_type']
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
    startkey = [domain, 'by_type', type_]
    endkey = startkey + [{}]
    submissions = XFormInstance.view(
        "couchforms/all_submissions_by_domain",
        startkey=startkey,
        endkey=endkey,
        reduce=True,
    ).one()
    return submissions['value'] if submissions else 0


def get_number_of_forms_of_all_types(domain):
    startkey = [domain, 'by_type']
    endkey = startkey + [{}]
    submissions = XFormInstance.view(
        "couchforms/all_submissions_by_domain",
        startkey=startkey,
        endkey=endkey,
        reduce=True,
    ).one()
    return submissions['value'] if submissions else 0


def get_forms_in_date_range(domain, start, end):
    # arbitrary hard limit of 10,000; can expand if this disturbs anything
    limit = 10000
    forms = XFormInstance.view(
        "couchforms/all_submissions_by_domain",
        startkey=[domain, "by_date", start.isoformat()],
        endkey=[domain, "by_date", end.isoformat(), {}],
        include_docs=True,
        reduce=False,
        limit=limit + 1
    ).all()
    if len(forms) > limit:
        forms.pop(limit)
        raise ViewTooLarge(forms)
    return forms


def clear_all_forms(domain):
    items = get_forms_of_all_types(domain)
    for item in items:
        item.delete()
