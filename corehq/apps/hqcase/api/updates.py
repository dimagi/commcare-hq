import uuid

import jsonobject
from jsonobject.exceptions import BadValueError
from memoized import memoized

from casexml.apps.case.mock import CaseBlock, IndexAttrs

from corehq.apps.hqcase.utils import CASEBLOCK_CHUNKSIZE, submit_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from .core import SubmissionError, UserError


def is_simple_dict(d):
    if not isinstance(d, dict) or not all(isinstance(v, str) for v in d.values()):
        raise BadValueError("Case properties must be strings")


class JsonIndex(jsonobject.JsonObject):
    case_id = jsonobject.StringProperty()
    temporary_id = jsonobject.StringProperty()
    case_type = jsonobject.StringProperty(required=True)
    relationship = jsonobject.StringProperty(required=True, choices=('child', 'extension'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not (bool(self.case_id) ^ bool(self.temporary_id)):
            raise BadValueError("You must set either case_id or temporary_id, and not both.")


class BaseJsonCaseChange(jsonobject.JsonObject):
    case_name = jsonobject.StringProperty()
    case_type = jsonobject.StringProperty()
    external_id = jsonobject.StringProperty()
    user_id = jsonobject.StringProperty(required=True)
    owner_id = jsonobject.StringProperty()
    properties = jsonobject.DictProperty(validators=[is_simple_dict], default={})
    indices = jsonobject.DictProperty(JsonIndex)
    _is_case_creation = False

    _allow_dynamic_properties = False

    class Meta(object):
        # prevent JsonObject from auto-converting dates etc.
        string_conversions = ()

    @classmethod
    def wrap(self, obj):
        for attr, _ in obj.items():
            if attr not in self._properties_by_key:
                # JsonObject will raise an exception here anyways, but we need
                # a user-friendly error message
                raise BadValueError(f"'{attr}' is not a valid field.")
        return super().wrap(obj)

    def get_caseblock(self):

        def _if_specified(value):
            return value if value is not None else CaseBlock.undefined

        return CaseBlock(
            case_id=self.get_case_id(),
            user_id=self.user_id,
            case_type=_if_specified(self.case_type),
            case_name=_if_specified(self.case_name),
            external_id=_if_specified(self.external_id),
            owner_id=_if_specified(self.owner_id),
            create=self._is_case_creation,
            update=dict(self.properties),
            index={
                name: IndexAttrs(index.case_type, index.case_id, index.relationship)
                for name, index in self.indices.items()
            },
        ).as_text()


class JsonCaseCreation(BaseJsonCaseChange):
    temporary_id = jsonobject.StringProperty()

    # overriding from subclass to mark these required
    case_name = jsonobject.StringProperty(required=True)
    case_type = jsonobject.StringProperty(required=True)
    owner_id = jsonobject.StringProperty(required=True)

    _is_case_creation = True

    @memoized
    def get_case_id(self):
        return str(uuid.uuid4())


class JsonCaseUpdate(BaseJsonCaseChange):
    case_id = jsonobject.StringProperty(required=True)
    _is_case_creation = False

    def get_case_id(self):
        return self.case_id


def handle_case_update(domain, data, user, device_id, case_id=None):
    is_bulk = isinstance(data, list)
    if is_bulk:
        updates = _get_bulk_updates(domain, data, user)
    else:
        updates = [_get_individual_update(domain, data, user, case_id)]

    xform, cases = _submit_case_updates(updates, domain, user, device_id)
    if xform.is_error:
        raise SubmissionError(xform.problem, xform.form_id,)

    if is_bulk:
        return xform, cases
    else:
        return xform, cases[0]


def _get_individual_update(domain, data, user, case_id=None):
    if case_id is not None and _missing_cases(domain, [case_id]):
        raise UserError(f"No case found with ID '{case_id}'")

    try:
        return _get_case_update(data, user.user_id, case_id)
    except BadValueError as e:
        raise UserError(str(e))


def _get_bulk_updates(domain, all_data, user):
    if len(all_data) > CASEBLOCK_CHUNKSIZE:
        raise UserError(f"You cannot submit more than {CASEBLOCK_CHUNKSIZE} updates in a single request")

    existing_ids = [c['case_id'] for c in all_data if isinstance(c, dict) and 'case_id' in c]
    missing = _missing_cases(domain, existing_ids)
    if missing:
        raise UserError(f"The following case IDs were not found: {', '.join(missing)}")

    updates = []
    errors = []
    for i, data in enumerate(all_data, start=1):
        try:
            update = _get_case_update(data, user.user_id, data.pop('case_id', None))
            updates.append(update)
        except BadValueError as e:
            errors.append(f'Error in row {i}: {e}')

    populate_index_case_ids(updates)

    if errors:
        raise UserError("; ".join(errors))

    return updates


def _missing_cases(domain, case_ids):
    real_case_ids = CaseAccessors(domain).get_case_ids_that_exist(case_ids)
    return set(case_ids) - set(real_case_ids)


def populate_index_case_ids(updates):
    case_ids_by_temp_id = {
        update.temporary_id: update.get_case_id()
        for update in updates if getattr(update, 'temporary_id', None)
    }
    for update in updates:
        for index in update.indices.values():
            if index.temporary_id:
                try:
                    index.case_id = case_ids_by_temp_id[index.temporary_id]
                except KeyError:
                    raise UserError(f"Could not find a case with temporary ID '{index.temporary_id}'")


def _get_case_update(data, user_id, case_id=None):
    update_class = JsonCaseCreation if case_id is None else JsonCaseUpdate
    additonal_args = {'user_id': user_id}
    if case_id is not None:
        additonal_args['case_id'] = case_id
    return update_class.wrap({**data, **additonal_args})


def _submit_case_updates(updates, domain, user, device_id):
    return submit_case_blocks(
        case_blocks=[update.get_caseblock() for update in updates],
        domain=domain,
        username=user.username,
        user_id=user.user_id,
        xmlns='http://commcarehq.org/case_api',
        device_id=device_id,
    )
