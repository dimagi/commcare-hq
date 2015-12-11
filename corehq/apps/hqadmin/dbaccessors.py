from corehq.dbaccessors.couchapps.all_docs import get_doc_count_by_type, \
    get_all_docs_with_doc_types
from corehq.util.test_utils import unit_testing_only
from couchforms.models import XFormInstance


@unit_testing_only
def get_all_forms_in_all_domains():
    return get_all_docs_with_doc_types(XFormInstance.get_db(), 'XFormInstance')


def get_number_of_forms_in_all_domains():
    """
    Return number of non-error forms (but incl. logs) total across all domains
    specifically as stored in couch.

    (Can't rewrite to pull from ES or SQL; this function is used as a point
    of comparison between row counts in other stores.)

    """

    return get_doc_count_by_type(XFormInstance.get_db(), 'XFormInstance')
