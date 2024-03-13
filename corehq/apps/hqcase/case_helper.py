import uuid
from dataclasses import dataclass
from django.utils.translation import gettext_lazy as _
from soil import DownloadBase

from corehq.apps.users.models import CouchUser
from casexml.apps.case.mock import CaseBlock, IndexAttrs
from corehq.apps.hqcase.utils import get_deidentified_data
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.form_processor.models import CommCareCase

from .api.updates import BaseJsonCaseChange, handle_case_update


@dataclass
class UserDuck:
    """Quacks like a User"""
    user_id: str
    username: str


class CaseHelper:
    """
    CaseHelper aims to offer a simple interface for simple operations on
    a single case. (For managing caseblock submissions for many cases,
    take a look at `SubmitCaseBlockHandler`.)

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


class CaseCopier:
    """A helper class for copying cases."""
    COMMCARE_CASE_COPY_PROPERTY_NAME = "commcare_case_copy"

    def __init__(self, domain, *, to_owner, censor_data=None):
        """
        Initialize ``CaseCopier``

        :param domain: The domain name
        :param to_owner: The ID of the CouchUser who will own the new
            cases.
        :param censor_data: A dictionary, where keys are the case
            attributes and case properties to be de-identified, and
            values are the de-id function to use. See
            ``corehq.apps.export.const.DEID_TRANSFORM_FUNCTIONS``
        """
        from corehq.apps.case_importer.do_import import SubmitCaseBlockHandler
        self.domain = domain
        self.to_owner = to_owner
        self.censor_data = censor_data or {}

        self.original_cases = {}  # {case_id: commcare_case}
        self.processed_cases = {}  # {orig_case_id: new_caseblock}

        system_user = UserDuck(user_id=SYSTEM_USER_ID, username='system')
        self.submission_handler = SubmitCaseBlockHandler(
            self.domain,
            import_results=None,
            case_type=None,
            user=system_user,
            record_form_callback=None,
            throttle=True,
            add_inferred_props_to_schema=False,
        )
        self.row_count = 0

    def copy_cases(self, case_ids, progress_task=None):
        """
        Copies the cases specified by ``case_ids`` to ``self.to_owner``.

        :param case_ids: The case IDs of the cases to copy.
        :param progress_task: The task which tracks the progress of this method
        :returns: A list of original- and new case ID pairs and a list
            of any errors encountered.
        """
        if not self.to_owner:
            return [], [_('Must copy cases to valid new owner')]

        original_cases = CommCareCase.objects.get_cases(
            case_ids,
            self.domain,
        )
        if not original_cases:
            return [], []
        self.original_cases = {c.case_id: c for c in original_cases}
        self.processed_cases = {}

        errors = []
        for idx, orig_case in enumerate(original_cases):
            if orig_case.owner_id == self.to_owner:
                errors.append(_(
                    'Original case owner {owner_id} cannot copy '
                    'case {case_id} to themselves'
                ).format(
                    owner_id=orig_case.owner_id,
                    case_id=orig_case.case_id,
                ))
                continue
            if orig_case.case_id not in self.processed_cases:
                caseblock = self._create_caseblock(orig_case)
                self.processed_cases[orig_case.case_id] = caseblock
                self._add_to_submission_handler(caseblock)

            if progress_task is not None:
                DownloadBase.set_progress(progress_task, idx, len(case_ids))

        self._commit_cases()

        orig_new_case_id_pairs = [
            (orig_case_id, caseblock.case_id)
            for orig_case_id, caseblock in self.processed_cases.items()
        ]
        return orig_new_case_id_pairs, errors

    def _create_caseblock(self, case):
        deid_attrs, deid_props = get_deidentified_data(case, self.censor_data)
        case_name = deid_attrs.get('case_name') or deid_attrs.get('name')
        index_map = self._get_new_index_map(case)
        # TODO: Are there any deid_attrs we care about other than
        #       case_name, name, external_id and date_opened?
        return CaseBlock(
            create=True,
            case_id=uuid.uuid4().hex,
            owner_id=self.to_owner,
            case_name=case_name or case.name,
            case_type=case.type,
            update={
                self.COMMCARE_CASE_COPY_PROPERTY_NAME: case.case_id,
                **case.case_json, **deid_props
            },
            index=index_map,
            external_id=deid_attrs.get('external_id', case.external_id),
            date_opened=deid_attrs.get('date_opened', case.opened_on),
            user_id=SYSTEM_USER_ID,
        )

    def _get_new_index_map(self, case):
        orig_index_map = case.get_index_map()
        new_index_map = {}
        for identifier, orig_index_dict in orig_index_map.items():
            new_index_attrs = self._get_new_index_attrs(orig_index_dict)
            if new_index_attrs:
                new_index_map[identifier] = new_index_attrs
        return new_index_map

    def _get_new_index_attrs(self, index_dict):
        index_dict = index_dict.copy()  # Don't change original by reference
        orig_parent_case_id = index_dict['case_id']

        # We need the copied case's case_id for the new index
        if orig_parent_case_id in self.processed_cases:
            new_parent_caseblock = self.processed_cases[orig_parent_case_id]
            index_dict['case_id'] = new_parent_caseblock.case_id
        else:
            # Need to process the referenced case first to get the
            # case_id of the copied case
            if orig_parent_case_id not in self.original_cases:
                return None

            orig_parent_case = self.original_cases[orig_parent_case_id]
            new_parent_caseblock = self._create_caseblock(orig_parent_case)
            self._add_to_submission_handler(new_parent_caseblock)
            self.processed_cases[orig_parent_case_id] = new_parent_caseblock

            index_dict['case_id'] = new_parent_caseblock.case_id

        return IndexAttrs(
            index_dict['case_type'],
            index_dict['case_id'],
            index_dict['relationship'],
        )

    def _add_to_submission_handler(self, caseblock):
        from corehq.apps.case_importer.do_import import RowAndCase
        self.submission_handler.add_caseblock(
            RowAndCase(row=self.row_count, case=caseblock)
        )
        self._increment_submission_row_count()

    def _commit_cases(self):
        self.submission_handler.commit_caseblocks()

    def _increment_submission_row_count(self):
        self.row_count += 1
