import uuid
from dataclasses import dataclass

from corehq.apps.users.models import CouchUser
from corehq.form_processor.models.cases import CommCareCase
from corehq.apps.hqcase.utils import submit_case_blocks, get_deidentified_data
from casexml.apps.case.mock import CaseBlock

from .api.updates import BaseJsonCaseChange, handle_case_update


class CaseHelper:
    """
    CaseHelper aims to offer a simple interface for simple operations on
    cases.

    Initialize ``CaseHelper`` with an existing case ... ::

        domain = 'hawaiian-mythology'
        helper = CaseHelper(case=case, domain=domain)

    ... or with a case ID ... ::

        helper = CaseHelper(case_id=case_id, domain=domain)

    ... or create a new case::

        helper = CaseHelper(domain=domain)
        helper.create_case({
            'case_type': 'child',
            'case_name': 'Namaka',
        })

    The helper's case is accessible at ``helper.case``.

    You can also create a new case using serialized case data returned
    by the Case API v0.6 ``serialize_case()`` function. Pass
    ``is_serialized=True`` for the CaseHelper to drop attributes from
    the data that are invalid for creating a new case. The new case will
    have a new case_id. The original case will be unaffected. ::

        case_data = serialize_case(helper.case)

        helper = CaseHelper(domain=domain)  # New helper for new case
        helper.create_case(case_data, is_serialized=True)

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
        is_serialized=False,
    ):
        assert self.case is None, '`self.case` already exists'

        if is_serialized:
            case_data = self._clean_serialized_case(case_data)
        else:
            case_data = case_data.copy()
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
        is_serialized=False,
    ):
        if not case_data:
            return

        assert self.case, '`self.case` is not defined'

        if is_serialized:
            case_data = self._clean_serialized_case(case_data)
        else:
            case_data = case_data.copy()
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

    @classmethod
    def copy_cases(
        cls,
        domain,
        case_ids,
        to_owner,
        censor_data=None,
        count_only=False
    ):
        """
        Copies the cases governed by 'case_ids' to the respective 'to_owner'
        and replacing the relevant case properties with the specified 'replace_props'
        on the copied cases (useful for hiding sensitive data).

        :param domain: the domain string
        :param case_ids: case ids of the cases to copy
        :param to_owner: the owner to copy the cases to
        :param censor_data: the attributes/properties to be censored, specified as a dict.
                The keys corresponding to the property/attribute and the value specifies
                the type of censored data, i.e. number or date
        :param count_only: specifies whether to return only the number of copied cases.

        :return: The copied cases. If `count_only` is True only the count will be returned.
        """
        if not to_owner:
            raise Exception('Must copy cases to valid new owner')

        original_cases = CommCareCase.objects.get_cases(case_ids=case_ids, domain=domain)
        if not any(original_cases):
            return []

        processed_cases = {}
        copied_cases_case_blocks = []

        def _get_new_identifier_index(case_identifier_index):
            _identifier_index = {**case_identifier_index}
            original_referenced_id = _identifier_index['case_id']

            # We need the copied case's case_id for the new index
            if original_referenced_id in processed_cases:
                _identifier_index['case_id'] = processed_cases[original_referenced_id].case_id
            else:
                # Need to process the referenced case first to get the case_id of the copied case
                try:
                    original_parent_case = next((
                        orig_case for orig_case in original_cases if orig_case.case_id == original_referenced_id
                    ))
                except StopIteration:
                    return {}
                referenced_case_block = _process_case(original_parent_case)
                _identifier_index['case_id'] = referenced_case_block.case_id
            return (
                _identifier_index['case_type'],
                _identifier_index['case_id'],
                _identifier_index['relationship'],
            )

        def _get_new_index_map(_case):
            new_case_index = {}
            for identifier in _case.get_index_map():
                identifier_index = _get_new_identifier_index(
                    _case.get_index_map()[identifier]
                )
                if identifier_index:
                    new_case_index[identifier] = identifier_index
            return new_case_index

        def _process_case(_case):
            if _case.case_id in processed_cases:
                return

            censored_attributes, censored_properties = get_deidentified_data(_case, censor_data)
            case_block = CaseBlock(
                create=True,
                case_id=uuid.uuid4().hex,
                owner_id=to_owner,
                case_name=censored_attributes.get('case_name', _case.name),
                case_type=_case.type,
                update={**_case.case_json, **censored_properties},
                index=_get_new_index_map(_case),
                external_id=censored_attributes.get('external_id', _case.external_id),
                date_opened=censored_attributes.get('date_opened', _case.opened_on),
            )

            copied_cases_case_blocks.append(case_block.as_text())
            processed_cases[_case.case_id] = case_block

            return case_block

        for c in original_cases:
            if c.owner_id == to_owner:
                raise Exception("Cannot copy case to self")
            _process_case(c)

        _, cases = submit_case_blocks(
            case_blocks=copied_cases_case_blocks,
            domain=domain,
        )

        if count_only:
            return len(cases)
        else:
            return cases

    @staticmethod
    def _clean_serialized_case(case_data):
        """
        Given the output of Case API v0.6's ``serialize_case()``,
        returns a new dictionary with invalid fields omitted.

        >>> case_data = {
        ...     'case_id': 'abc123',
        ...     'domain': 'test',
        ...     'external_id': '(136108) 2003 EL61 II',
        ... }
        >>> CaseHelper._clean_serialized_case(case_data)
        {'external_id': '(136108) 2003 EL61 II'}

        """
        valid_fields = CaseHelper._get_valid_fields()
        return {k: v for k, v in case_data.items() if k in valid_fields}

    @staticmethod
    def _get_valid_fields():
        # Use `BaseJsonCaseChange` instead of `JsonCaseCreation`,
        # because `JsonCaseCreation` adds a `temporary_id` property for
        # bulk updates, which `CaseHelper` does not support.
        return set(BaseJsonCaseChange._properties_by_key) - {'case_id'}

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
