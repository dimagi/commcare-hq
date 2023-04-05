from couchdbkit import ResourceNotFound
from jsonschema import validate

from casexml.apps.case.mock import CaseBlock, IndexAttrs

from corehq.apps.users.models import CouchUser

from .utils import SYSTEM_FORM_XMLNS, submit_case_blocks

case_block_args_case_properties = {
    'owner_id',
    'external_id',
    'case_type',
    'case_name',
}


class CaseHelper:
    """
    CaseHelper aims to offer a simple interface for simple operations on
    cases.

    Initialize ``CaseHelper`` with an existing case::

        helper = CaseHelper(case)

    Or create a case using data in the format returned by
    ``CommCareCase.to_api_json(lite=True)``::

        helper = CaseHelper()
        helper.create_case({
            'case_id': uuid4().hex,
            'domain': 'hawaiian-mythology',
            'properties': {
                'case_name': 'Namaka',
                'case_type': 'child',
            },
        })

    Update the case::

        helper.update(properties={'description': 'Goddess of the sea'})

    Add an index::

        helper.update(indices={'mother': {
            'case_id': mother.case_id,
            'case_type': mother.type,
            'relationship': 'child',
        }})

    Close the case::

        helper.close()

    ``create_case()``, ``update()``, and ``close()`` methods all accept
    ``user_id``, ``device_id`` and ``xmlns`` parameters to identify
    who/what called the operation. Under the hood, all operations use
    ``submit_case_blocks()`` to submit forms.

    """

    def __init__(self, case=None):
        self.case = case

    def create_case(
        self,
        case_api_json,
        *,
        user_id=None,
        device_id='corehq.apps.hqcase.case_helper.CaseHelper',
        xmlns=SYSTEM_FORM_XMLNS,
    ):
        assert self.case is None, 'CaseHelper.case already exists'
        validate_case_api_json(case_api_json)

        case_block = self._get_create_case_block(case_api_json)
        kwargs = self._get_submit_kwargs(user_id)
        xform, cases = submit_case_blocks(
            [case_block],
            case_api_json['domain'],
            device_id=device_id,
            xmlns=xmlns,
            **kwargs,
        )
        (self.case,) = cases

    def _get_create_case_block(self, case_api_json):
        kwargs = {
            arg: case_api_json['properties'][arg]
            for arg in case_block_args_case_properties
            if arg in case_api_json['properties']
        }
        update = {
            k: v for k, v in case_api_json['properties'].items()
            if k not in case_block_args_case_properties
        }
        if case_api_json.get('indices'):
            index = {
                index_id: IndexAttrs(
                    case_type=attrs['case_type'],
                    case_id=attrs['case_id'],
                    relationship=attrs['relationship'],
                )
                for index_id, attrs in case_api_json['indices'].items()
            }
            kwargs['index'] = index
        if case_api_json.get('user_id'):
            kwargs['user_id'] = case_api_json['user_id']
        if 'closed' in case_api_json:
            kwargs['close'] = case_api_json['closed']

        case_block = CaseBlock(
            case_api_json['case_id'],
            create=True,
            update=update,
            domain=case_api_json['domain'],
            **kwargs,
        )
        return case_block.as_text()

    def update(
        self,
        *,
        properties=None,
        indices=None,
        user_id=None,
        device_id='corehq.apps.hqcase.case_helper.CaseHelper',
        xmlns=SYSTEM_FORM_XMLNS,
    ):
        assert self.case, 'CaseHelper.case is not defined'

        case_block = self._get_update_case_block(properties, indices, user_id)
        kwargs = self._get_submit_kwargs(user_id)
        xform, cases = submit_case_blocks(
            [case_block],
            self.case.domain,
            device_id=device_id,
            xmlns=xmlns,
            **kwargs,
        )
        (self.case,) = cases

    def _get_update_case_block(self, properties, indices, user_id):
        if properties:
            kwargs = {
                arg: properties[arg]
                for arg in case_block_args_case_properties
                if arg in properties
            }
            update = {
                k: v for k, v in properties.items()
                if k not in case_block_args_case_properties
            }
            kwargs['update'] = update
        else:
            kwargs = {}
        if indices:
            index = {
                index_id: IndexAttrs(
                    case_type=attrs['case_type'],
                    case_id=attrs['case_id'],
                    relationship=attrs['relationship'],
                )
                for index_id, attrs in indices.items()
            }
            kwargs['index'] = index
        if user_id:
            kwargs['user_id'] = user_id

        case_block = CaseBlock(
            self.case.case_id,
            domain=self.case.domain,
            **kwargs,
        )
        return case_block.as_text()

    def close(
        self,
        *,
        user_id=None,
        device_id='corehq.apps.hqcase.case_helper.CaseHelper',
        xmlns=SYSTEM_FORM_XMLNS,
    ):
        assert self.case, 'CaseHelper.case is not defined'

        case_block = CaseBlock(
            self.case.case_id,
            close=True,
        ).as_text()
        kwargs = self._get_submit_kwargs(user_id)
        xform, cases = submit_case_blocks(
            [case_block],
            self.case.domain,
            device_id=device_id,
            xmlns=xmlns,
            **kwargs,
        )
        (self.case,) = cases

    def _get_submit_kwargs(self, user_id):
        kwargs = {}
        if user_id:
            kwargs['user_id'] = user_id
            try:
                user = CouchUser.get(user_id)
                kwargs['username'] = user.username
            except ResourceNotFound:
                pass
        return kwargs


def validate_case_api_json(case_api_json):
    """
    Checks whether ``case_api_json`` looks like the output of
    ``CommCareCase.to_api_json(lite=True)``.

    Raises ``jsonschema.ValidationError`` on failure.

    >>> case_api_json = {
    ...     'case_id': 'a96b328be74e4cbbbc67b087e2a21bf1',
    ...     'closed': False,
    ...     'domain': 'test-domain',
    ...     'indices': {
    ...         'mother': {
    ...             'case_id': '1581a5deeff74ce2910d98e472e6d206',
    ...             'case_type': 'mother',
    ...             'relationship': 'child',
    ...         },
    ...     },
    ...     'properties': {
    ...         'case_name': 'Namaka',
    ...         'case_type': 'child',
    ...         'external_id': None,
    ...     },
    ...     'user_id': '',
    ... }
    >>> validate_case_api_json(case_api_json)

    """
    schema = {
        'type': 'object',
        'properties': {
            'attachments': {'type': 'object'},
            'case_id': {'type': 'string'},
            'closed': {'type': 'boolean'},
            'date_closed': {'type': ['string', 'null']},
            'date_modified': {'type': 'string'},
            'domain': {'type': 'string'},
            'indices': {
                'type': 'object',
                'additionalProperties': {
                    'type': 'object',
                    'properties': {
                        'case_id': {'type': 'string'},
                        'case_type': {'type': 'string'},
                        'relationship': {'type': 'string'},
                    },
                    'required': [
                        'case_id',
                        'case_type',
                        'relationship',
                    ],
                }
            },
            'properties': {
                'type': 'object',
                'properties': {
                    'case_name': {'type': 'string'},
                    'case_type': {'type': 'string'},
                    'date_opened': {},  # `datetime.datetime`
                    'external_id': {'type': ['string', 'null']},
                    'owner_id': {'type': 'string'},
                },
                'required': [
                    'case_name',
                    'case_type',
                ],
            },
            'server_date_modified': {'type': 'string'},
            'user_id': {'type': 'string'},
            'xform_ids': {
                'type': 'array',
                'items': {'type': 'string'},
            },
        },
        'required': [
            'case_id',
            'domain',
            'properties',
        ],
    }
    validate(instance=case_api_json, schema=schema)
