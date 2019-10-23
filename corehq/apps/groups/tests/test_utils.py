from corehq.apps.groups.models import Group
from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types
from corehq.util.test_utils import unit_testing_only


@unit_testing_only
def delete_all_groups():
    all_groups = list(get_all_docs_with_doc_types(Group.get_db(), ['Group', 'Group-Deleted']))
    Group.get_db().delete_docs(all_groups)
