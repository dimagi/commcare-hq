from casexml.apps.case.models import CommCareCase
from corehq.util.couch_helpers import paginate_view
from couchforms.models import XFormInstance
from django.conf import settings


def get_all_forms_in_all_domains():
    assert settings.UNIT_TESTING, (
        'You can only call {} when unit testing'
        .format(get_all_forms_in_all_domains.__name__)
    )
    return XFormInstance.view(
        'hqadmin/forms_over_time',
        reduce=False,
        include_docs=True,
    ).all()


def get_number_of_forms_in_all_domains():
    """
    Return number of non-error forms (but incl. logs) total across all domains
    specifically as stored in couch.

    (Can't rewrite to pull from ES or SQL; this function is used as a point
    of comparison between row counts in other stores.)

    """

    return XFormInstance.view('hqadmin/forms_over_time').one()['value']


def iter_all_forms_most_recent_first(chunk_size=100):
    return paginate_view(
        XFormInstance.get_db(),
        'hqadmin/forms_over_time',
        reduce=False,
        include_docs=True,
        descending=True,
        chunk_size=chunk_size,
    )


def iter_all_cases_most_recent_first(chunk_size=100):
    return paginate_view(
        CommCareCase.get_db(),
        'hqadmin/cases_over_time',
        reduce=False,
        include_docs=True,
        descending=True,
        chunk_size=chunk_size,
    )
