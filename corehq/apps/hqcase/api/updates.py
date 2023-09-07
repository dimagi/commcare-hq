import uuid

from django.utils.functional import cached_property
from django.core.exceptions import PermissionDenied

import jsonobject
from jsonobject.exceptions import BadValueError

from casexml.apps.case.mock import CaseBlock, IndexAttrs

from corehq.apps.fixtures.utils import is_identifier_invalid
from corehq.apps.hqcase.utils import CASEBLOCK_CHUNKSIZE, submit_case_blocks
from corehq.form_processor.models import CommCareCase
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.locations.models import SQLLocation
from corehq.apps.es.users import UserES
from corehq.apps.users.models import CouchUser

from .core import SubmissionError, UserError


def valid_properties_dict(d):
    for k, v in d.items():
        if is_identifier_invalid(k):
            raise BadValueError(f"Error with case property '{k}'. "
                                "Case property names must be valid XML identifiers.")
        elif not isinstance(v, str):
            raise BadValueError(f"Error with case property '{k}'. "
                                f"Values must be strings, received '{v}'")


def valid_indices_dict(d):
    for k in d.keys():
        if is_identifier_invalid(k):
            raise BadValueError(f"Error with index '{k}'. "
                                "Index names must be valid XML identifiers.")


class JsonIndex(jsonobject.JsonObject):
    case_id = jsonobject.StringProperty()
    external_id = jsonobject.StringProperty()
    temporary_id = jsonobject.StringProperty()
    case_type = jsonobject.StringProperty()
    relationship = jsonobject.StringProperty(choices=('child', 'extension'))

    def validate(self, *args, **kwargs):
        ids_specified = len(list(filter(None, [self.case_id, self.external_id, self.temporary_id])))
        if ids_specified > 1:
            raise BadValueError("Indices must specify case_id, external_id, or temporary ID, and only one")
        if ids_specified == 1:
            for prop in ['case_type', 'relationship']:
                if not self[prop]:
                    raise BadValueError(f"Property {prop} is required when creating or updating case indices")
        super().validate(*args, **kwargs)

    def get_id(self, case_db):
        if self.temporary_id:
            return case_db.get_by_temporary_id(self.temporary_id)
        if self.external_id:
            return case_db.get_by_external_id(self.external_id)
        # case_id may be unspecified, which is fine - that's how deletions work
        return self.case_id


class BaseJsonCaseChange(jsonobject.JsonObject):
    case_id = jsonobject.StringProperty()
    case_name = jsonobject.StringProperty()
    case_type = jsonobject.StringProperty()
    external_id = jsonobject.StringProperty()
    user_id = jsonobject.StringProperty(required=True)
    owner_id = jsonobject.StringProperty()
    properties = jsonobject.DictProperty(validators=[valid_properties_dict], default={})
    indices = jsonobject.DictProperty(JsonIndex, validators=[valid_indices_dict])
    close = jsonobject.BooleanProperty(default=False)
    _is_case_creation = False

    _allow_dynamic_properties = False

    class Meta(object):
        # prevent JsonObject from auto-converting dates etc.
        string_conversions = ()

    @classmethod
    def wrap(cls, data):
        for attr, _ in data.items():
            if attr not in cls._properties_by_key:
                # JsonObject will raise an exception here anyways, but we need
                # a user-friendly error message
                raise BadValueError(f"'{attr}' is not a valid field.")
        return super().wrap(data)

    def get_caseblock(self, case_db):

        def get_kwargs(*attribs):
            return {
                a: getattr(self, a)
                for a in attribs
                if getattr(self, a) is not None
            }

        return CaseBlock(
            case_id=self.get_case_id(case_db),
            user_id=self.user_id,
            create=self._is_case_creation,
            update=dict(self.properties),
            close=self.close,
            index={
                name: IndexAttrs(
                    case_type=index.case_type,
                    case_id=index.get_id(case_db),
                    relationship=index.relationship
                ) for name, index in self.indices.items()
            },
            **get_kwargs('case_type', 'case_name', 'external_id', 'owner_id'),
        ).as_text()

    @property
    def is_new_case(self):
        return self._is_case_creation


class JsonCaseCreation(BaseJsonCaseChange):
    temporary_id = jsonobject.StringProperty()

    # overriding from subclass to mark these required
    case_name = jsonobject.StringProperty(required=True)
    case_type = jsonobject.StringProperty(required=True)
    owner_id = jsonobject.StringProperty(required=True)

    _is_case_creation = True

    @classmethod
    def wrap(cls, data):
        if 'case_id' in data:
            raise UserError("You cannot specify case_id when creating a new case")
        data['case_id'] = str(uuid.uuid4())
        return super().wrap(data)

    def get_case_id(self, case_db):
        return self.case_id


class JsonCaseUpdate(BaseJsonCaseChange):
    _is_case_creation = False

    def validate(self, *args, **kwargs):
        super().validate(*args, **kwargs)
        if not self.case_id and not self.external_id:
            raise BadValueError("Case updates must provide either a case_id or external_id")

    def get_case_id(self, case_db):
        if self.case_id:
            if self.case_id in case_db.real_case_ids:
                return self.case_id
            raise UserError(f"No case found with ID '{self.case_id}'")

        return case_db.get_by_external_id(self.external_id)


def handle_case_update(domain, data, user, device_id, is_creation):
    is_bulk = isinstance(data, list)
    if is_bulk:
        updates = _get_bulk_updates(domain, data, user)
    else:
        updates = [_get_individual_update(domain, data, user, is_creation)]

    case_db = CaseIDLookerUpper(domain, updates)

    if isinstance(user, CouchUser):
        validate_update_permission(domain, updates, user, case_db)

    case_blocks = [update.get_caseblock(case_db) for update in updates]
    xform, cases = _submit_case_blocks(case_blocks, domain, user, device_id)
    if xform.is_error:
        raise SubmissionError(xform.problem, xform.form_id,)

    if is_bulk:
        return xform, cases
    else:
        return xform, cases[0]


def _get_individual_update(domain, data, user, is_creation):
    update_class = JsonCaseCreation if is_creation else JsonCaseUpdate
    data['user_id'] = user.user_id
    try:
        update = update_class.wrap(data)
    except BadValueError as e:
        raise UserError(str(e))
    return update


def _get_bulk_updates(domain, all_data, user):
    if len(all_data) > CASEBLOCK_CHUNKSIZE:
        raise UserError(f"You cannot submit more than {CASEBLOCK_CHUNKSIZE} updates in a single request")

    updates = []
    errors = []
    for i, data in enumerate(all_data, start=1):
        try:
            is_creation = data.pop('create', None)
            if is_creation is None:
                raise UserError("A 'create' flag is required for each update.")
            updates.append(_get_individual_update(domain, data, user, is_creation))
        except UserError as e:
            errors.append(f'Error in row {i}: {e}')

    if errors:
        raise UserError("; ".join(errors))

    return updates


class CaseIDLookerUpper:
    def __init__(self, domain, updates):
        self.domain = domain
        self.updates = updates

    @cached_property
    def real_case_ids(self):
        case_ids = filter(None, (getattr(update, 'case_id', None) for update in self.updates))
        return set(CommCareCase.objects.get_case_ids_that_exist(self.domain, case_ids))

    def get_by_temporary_id(self, key):
        try:
            return self._by_temporary_id[key]
        except KeyError:
            raise UserError(f"Could not find a case with temporary_id '{key}'")

    @cached_property
    def _by_temporary_id(self):
        return {
            update.temporary_id: update.case_id
            for update in self.updates
            if getattr(update, 'temporary_id', None) and update.case_id
        }

    def get_by_external_id(self, key):
        try:
            return self._by_external_id[key]
        except KeyError:
            raise UserError(f"Could not find a case with external_id '{key}'")

    @cached_property
    def _by_external_id(self):
        ids_in_request = {
            update.external_id: update.case_id
            for update in self.updates if update.external_id and update.case_id
        }

        ids_to_find = {
            update.external_id for update in self.updates
            if not update._is_case_creation and not update.case_id
        } | {
            index.external_id for update in self.updates for index in update.indices.values()
        }
        ids_to_find -= set(ids_in_request)
        ids_looked_up = self._get_case_ids_by_external_id(ids_to_find)

        return {**ids_in_request, **ids_looked_up}

    def _get_case_ids_by_external_id(self, external_ids):
        external_ids = list(filter(None, external_ids))

        case_ids_by_external_id = {}
        for db_name in get_db_aliases_for_partitioned_query():
            query = (CommCareCase.objects.using(db_name)
                     .filter(domain=self.domain, external_id__in=external_ids)
                     .values_list('external_id', 'case_id'))
            for external_id, case_id in query:
                if external_id in case_ids_by_external_id:
                    raise UserError(f"There are multiple cases with external_id {external_id}")
                case_ids_by_external_id[external_id] = case_id

        return case_ids_by_external_id

    def get_owner_id(self, key):
        try:
            return self._get_owner_id[key]
        except KeyError:
            raise UserError(f"Could not find an owner_id with case_id '{key}'")

    @cached_property
    def _get_owner_id(self):
        return {
            update.case_id: update.owner_id
            for update in self.updates if update.owner_id
        }


def _submit_case_blocks(case_blocks, domain, user, device_id):
    return submit_case_blocks(
        case_blocks=case_blocks,
        domain=domain,
        username=user.username,
        user_id=user.user_id,
        xmlns='http://commcarehq.org/case_api',
        device_id=device_id,
        max_wait=15
    )


def _get_owner_ids(domain, data, case_db):
    owner_ids = []
    case_ids = []
    for data_item in data:
        if data_item.owner_id:
            owner_ids.append(data_item.owner_id)
        if not data_item.is_new_case:
            case_id = data_item.get_case_id(case_db)
            case_ids.append(case_id)

        for index in data_item.indices.values():
            index_case_id = index.get_id(case_db)
            if index_case_id in case_db.real_case_ids:
                case_ids.append(index_case_id)
            else:
                case_owner_id = case_db.get_owner_id(index_case_id)
                owner_ids.append(case_owner_id)

    case_owner_ids = (
        CaseSearchES()
        .domain(domain)
        .case_ids(case_ids)
        .values_list('owner_id', flat=True)
    )
    return set(owner_ids + case_owner_ids)


def validate_update_permission(domain, data, user, case_db):
    """
    Check whether the given `user` has permission to create/update cases and indices from `data`.
    Also checks whether `user` has access to all case indices, if there are any.
    """
    if user.has_permission(domain, 'access_all_locations'):
        return

    all_owner_ids = _get_owner_ids(domain, data, case_db)

    # List of owner ids can contain either location or user ids, so separate the two
    location_ids = set(
        SQLLocation.objects
        .filter(location_id__in=all_owner_ids)
        .values_list('location_id', flat=True)
    )
    user_ids = all_owner_ids - set(location_ids)

    user_location_ids = set(
        SQLLocation.objects
        .accessible_to_user(domain, user)
        .values_list('location_id', flat=True)
    )

    inaccessible_location_ids = location_ids - user_location_ids
    if inaccessible_location_ids:
        raise PermissionDenied(
            "No permission to access following location ids "
            f"from given case/owner ids: {inaccessible_location_ids}"
        )

    # Get all user_ids that share a location with user
    users_with_shared_locations = set(
        UserES()
        .domain(domain)
        .user_ids(user_ids)
        .location(user_location_ids)
        .values_list('_id', flat=True)
    )
    inaccessible_user_ids = user_ids - set(users_with_shared_locations)
    if inaccessible_user_ids:
        raise PermissionDenied(
            "No permission to access following user ids "
            f"from given case/owner ids: {inaccessible_user_ids}"
        )

    # Can access all users at this point, so if length is different then some users could not be found
    if len(user_ids) != len(users_with_shared_locations):
        raise UserError("Not all owner_ids are real owner_ids in the project")
