from casexml.apps.case.tests.util import create_case
from corehq.apps.app_manager.const import USERCASE_TYPE


def create_usercase(user):
    """
    Returns a context manager that yields the user case and
    deletes it on exit.
    """
    return create_case(
        user.domain,
        USERCASE_TYPE,
        owner_id=user.get_id,
        external_id=user.get_id,
        update={'hq_user_id': user.get_id},
    )
