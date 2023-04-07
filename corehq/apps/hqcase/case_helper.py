from dataclasses import dataclass

from corehq.apps.users.models import CouchUser

from .api.updates import handle_case_update


class CaseHelper:
    """
    CaseHelper aims to offer a simple interface for simple operations on
    cases.

    Initialize ``CaseHelper`` with an existing case ... ::

        domain = 'hawaiian-mythology'
        helper = CaseHelper(case=case, domain=domain)

    ... or with a case ID::

        helper = CaseHelper(case_id=case_id, domain=domain)

    Or create a case using data in the format returned by the Case API
    v0.6 ``serialize_case()`` function::

        helper = CaseHelper(domain=domain)
        helper.create_case({
            'domain': 'hawaiian-mythology',
            'case_type': 'child',
            'case_name': 'Namaka',
        })

    Update case properties::

        helper.update({'properties': {
            'description': 'Goddess of the sea',
        }})

    Add an index::

        helper.update({'indices': {'mother': {
            'case_id': mother.case_id,
            'case_type': mother.type,
            'relationship': 'child',
        }}})

    Close the case::

        helper.close()

    ``create_case()``, ``update()``, and ``close()`` methods all accept
    ``user_id`` and ``device_id`` parameters to identify who/what called
    the operation. Under the hood, all operations use the Case API v0.6
    ``handle_case_update()`` function.

    """

    def __init__(self, *, domain, case=None, case_id=None):

        @dataclass
        class BriefCase:
            """Like a CommCareCase, but briefer."""
            case_id: str
            domain: str
            user_id: str = ''

        if case:
            assert not case_id or case.case_id == case_id, (
                '`case.case_id` does not match `case_id`')
            assert case.domain == domain, (
                f'`case.domain` {case.domain!r} does not match `domain` '
                f'{domain!r}')

            self.case = case
        elif case_id:
            self.case = BriefCase(case_id=case_id, domain=domain)
        else:
            self.case = None
        self.domain = domain

    def create_case(
        self,
        case_data,
        *,
        user_id=None,
        device_id='corehq.apps.hqcase.case_helper.CaseHelper',
    ):
        assert self.case is None, '`self.case` already exists'

        case_data = self._copy_case_data(case_data)
        user = self._get_user_duck(user_id, self.domain)
        case_data.setdefault('user_id', user.user_id)
        case_data.setdefault('owner_id', '')
        __, self.case = handle_case_update(
            self.domain,
            case_data,
            user=user,
            device_id=device_id,
            is_creation=True,
        )

    def update(
        self,
        case_data,
        *,
        user_id=None,
        device_id='corehq.apps.hqcase.case_helper.CaseHelper',
    ):
        if not case_data:
            return

        assert self.case, '`self.case` is not defined'

        case_data = self._copy_case_data(case_data)
        case_data['case_id'] = self.case.case_id
        user = self._get_user_duck(user_id, self.domain)
        case_data.setdefault('user_id', user.user_id)
        __, self.case = handle_case_update(
            self.domain,
            case_data,
            user=user,
            device_id=device_id,
            is_creation=False,
        )

    def close(
        self,
        *,
        user_id=None,
        device_id='corehq.apps.hqcase.case_helper.CaseHelper',
    ):
        assert self.case, '`self.case` is not defined'

        user = self._get_user_duck(user_id, self.domain)
        case_data = {
            'case_id': self.case.case_id,
            'user_id': self.case.user_id or user.user_id,
            'close': True,
        }
        __, self.case = handle_case_update(
            self.domain,
            case_data,
            user=self._get_user_duck(user_id, self.domain),
            device_id=device_id,
            is_creation=False,
        )

    @staticmethod
    def _copy_case_data(case_data):
        """
        Given the output of Case API v0.6's ``serialize_case()``,
        returns a new dictionary with invalid fields omitted.

        >>> case_data = {'case_id': 'abc123', 'domain': 'test', 'foo': 'bar'}
        >>> CaseHelper._copy_case_data(case_data)
        {'foo': 'bar'}

        """
        invalid_fields = {
            'case_id',
            'domain',
            'closed',
            'date_closed',
            'date_opened',
            'last_modified',
            'modified_by',
            'server_last_modified',
            'indexed_on',
        }
        return {k: v for k, v in case_data.items() if k not in invalid_fields}

    @staticmethod
    def _get_user_duck(user_id, domain):

        @dataclass
        class UserDuck:
            """Quacks like a User"""
            user_id: str
            username: str

        user_duck = UserDuck(user_id='', username='')
        if user_id:
            user_duck.user_id = user_id
            try:
                user = CouchUser.get_by_user_id(user_id, domain)
                if user:
                    user_duck.username = user.username
            except CouchUser.AccountTypeError:
                pass
        return user_duck
