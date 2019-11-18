from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types
from corehq.util.test_utils import unit_testing_only
from couchforms.models import XFormInstance


@unit_testing_only
def get_all_forms_in_all_domains():
    return [
        XFormInstance.wrap(doc)
        for doc in get_all_docs_with_doc_types(XFormInstance.get_db(), ['XFormInstance'])
    ]
