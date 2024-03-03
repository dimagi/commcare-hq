from unittest.mock import patch, PropertyMock

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.users.user_data import UserData


def create_usercase(user):
    """
    Returns a context manager that yields the user case and
    deletes it on exit.
    """

    from casexml.apps.case.tests.util import create_case
    return create_case(
        user.domain,
        USERCASE_TYPE,
        owner_id=user.get_id,
        external_id=user.get_id,
        update={'hq_user_id': user.get_id},
    )


patch_user_data_db_layer = patch('corehq.apps.users.user_data.UserData.for_user',
                                 new=lambda u, d: UserData({}, None, d))

patch_user_data_schema = patch('corehq.apps.users.user_data.UserData._schema_defaults',
                               new=PropertyMock(return_value={}))
