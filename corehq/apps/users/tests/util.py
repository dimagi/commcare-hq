from contextlib import ContextDecorator
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


def patch_user_data_db_layer(fn=None, *, user_schema=None):
    context = _patch_user_data_db_layer(user_schema=user_schema)
    return context(fn) if fn else context


class _patch_user_data_db_layer(ContextDecorator):
    def __init__(self, user_schema=None):
        self.user_schema = user_schema or {}
        self.init_patcher = None
        self.schema_patcher = None

    def __enter__(self):
        self.init_patcher = patch(
            'corehq.apps.users.user_data.UserData.for_user', new=lambda u, d: UserData({}, None, d))
        self.schema_patcher = patch('corehq.apps.users.user_data.UserData._schema_defaults',
                               new=PropertyMock(return_value=self.user_schema))
        self.init_patcher.start()
        self.schema_patcher.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.schema_patcher.stop()
        self.init_patcher.stop()
