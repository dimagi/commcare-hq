from six.moves import \
    filter  # keep unused import so py3 conversion scripts don't rewrite file

from casexml.apps.case.xform import is_device_report


def form_matches_users(form, users):
    try:
        return form['form']['meta']['userID'] in users
    except KeyError:
        return False


def is_commconnect_form(form):
    """
    Checks if something is a commconnect form, by manually inspecting the deviceID property
    """
    return form.get('form', {}).get('meta', {}).get('deviceID', None) == 'commconnect'


def default_form_filter(form, filter):
    # hack: all the other filters we use completely break on device logs
    # which don't have standard meta blocks, so just always force them
    # to be accepted, since the only time they are relevant is when they're
    # explicitly wanted
    return is_device_report(form) or filter(form)


def default_case_filter(doc):
    return doc["doc_type"] == "CommCareCase"
