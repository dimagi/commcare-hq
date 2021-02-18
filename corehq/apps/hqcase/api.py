import uuid

import jsonobject
from jsonobject.exceptions import BadValueError

from casexml.apps.case.mock import CaseBlock, IndexAttrs

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


def serialize_case(case):
    """Serializes a case for the V0.6 Case API"""
    return {
        "domain": case.domain,
        "@case_id": case.case_id,
        "@case_type": case.type,
        "case_name": case.name,
        "external_id": case.external_id,
        "@owner_id": case.owner_id,
        "date_opened": _isoformat(case.opened_on),
        "last_modified": _isoformat(case.modified_on),
        "server_last_modified": _isoformat(case.server_modified_on),
        "closed": case.closed,
        "date_closed": _isoformat(case.closed_on),
        "properties": dict(case.dynamic_case_properties()),
        "indices": {
            index.identifier: {
                "case_id": index.referenced_id,
                "@case_type": index.referenced_type,
                "@relationship": index.relationship,
            }
            for index in case.indices
        }
    }


def _isoformat(value):
    return value.isoformat() if value else None


def is_simple_dict(d):
    if not isinstance(d, dict) or not all(isinstance(v, str) for v in d.values()):
        raise BadValueError("Case properties must be strings")


class JsonIndex(jsonobject.JsonObject):
    case_id = jsonobject.StringProperty(required=True)
    case_type = jsonobject.StringProperty(name='@case_type', required=True)
    relationship = jsonobject.StringProperty(name='@relationship', required=True,
                                             choices=('child', 'extension'))


class BaseJsonCaseChange(jsonobject.JsonObject):
    case_name = jsonobject.StringProperty()
    external_id = jsonobject.StringProperty()
    user_id = jsonobject.StringProperty(required=True)
    owner_id = jsonobject.StringProperty(name='@owner_id')
    properties = jsonobject.DictProperty(validators=[is_simple_dict], default={})
    indices = jsonobject.DictProperty(JsonIndex)
    _is_case_creation = False

    _allow_dynamic_properties = False

    class Meta(object):
        # prevent JsonObject from auto-converting dates etc.
        string_conversions = ()

    def get_caseblock(self):

        def _if_specified(value):
            return value if value is not None else CaseBlock.undefined

        # ID and case type can't be changed
        case_id = str(uuid.uuid4()) if self._is_case_creation else self.case_id
        case_type = self.case_type if self._is_case_creation else CaseBlock.undefined

        return CaseBlock(
            case_id=case_id,
            user_id=self.user_id,
            case_type=case_type,
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
    case_type = jsonobject.StringProperty(name='@case_type', required=True)

    # overriding from subclass to mark these required
    case_name = jsonobject.StringProperty(required=True)
    owner_id = jsonobject.StringProperty(name='@owner_id', required=True)

    _is_case_creation = True


class JsonCaseUpdate(BaseJsonCaseChange):
    case_id = jsonobject.StringProperty(required=True)
    _is_case_creation = False


class UserError(Exception):
    pass


def handle_case_update(domain, data, user, device_id, case_id=None):
    is_bulk = isinstance(data, list)
    if is_bulk:
        updates = _get_bulk_updates(domain, data, user)
    else:
        updates = [_get_individual_update(domain, data, user, case_id)]

    xform, cases = _submit_case_updates(updates, domain, user, device_id)
    if is_bulk:
        return xform, cases
    else:
        return xform, cases[0] if cases else None


def _get_individual_update(domain, data, user, case_id=None):
    if case_id is not None and _missing_cases(domain, [case_id]):
        raise UserError(f"No case found with ID '{case_id}'")

    try:
        return _get_case_update(data, user.user_id, case_id)
    except BadValueError as e:
        raise UserError(str(e))


def _get_bulk_updates(domain, all_data, user):
    if len(all_data) > 100:
        raise UserError("You cannot submit more than 100 updates in a single request")

    existing_ids = [c['@case_id'] for c in all_data if isinstance(c, dict) and '@case_id' in c]
    missing = _missing_cases(domain, existing_ids)
    if missing:
        raise UserError(f"The following case IDs were not found: {', '.join(missing)}")

    updates = []
    errors = []
    for i, data in enumerate(all_data):
        try:
            update = _get_case_update(data, user.user_id, data.pop('@case_id', None))
            updates.append(update)
        except BadValueError as e:
            errors.append(f'Error in row {i}: {e}')

    if errors:
        raise UserError("; ".join(errors))

    return updates


def _missing_cases(domain, case_ids):
    return set(case_ids) - {
        case.case_id for case in
        CaseAccessors(domain).get_cases(case_ids)
        if case.domain == domain
    }


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
