from jsonobject.base_properties import DefaultProperty

from casexml.apps.case.const import UNOWNED_EXTENSION_OWNER_ID
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from dimagi.ext.jsonobject import JsonObject

from corehq.apps.userreports.specs import TypeProperty
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


class AWCOwnerId(JsonObject):
    """
    This class and subclasses are intended to allow us to use one expression
    for all case data sources and return the correct owner id of a case. It
    must also appropriately handle the case where some cases are in the
    original ICDS hierarchy (AWC owner id on every case) and the new hierarchy.

    REACH is proposing changing the case structure to rely on extension
    cases that do not include an owner on each case. The owner(s) will be
    determined by assignment cases that are extensions of the household.

    assignment (AWC) +------>household<------+ assignment (Village)
                               ^
                               |
                               +
                             person
                               ^
                               |
                               +
                    child_health/ccs_record
    """
    type = TypeProperty('aaa_awc_owner_id')
    case_id_expression = DefaultProperty(required=True)
    index_identifier = 'owner_awc'

    def configure(self, case_id_expression):
        self._case_id_expression = case_id_expression

    def __call__(self, item, context=None):
        case_id = self._case_id_expression(item, context)

        if not case_id:
            return None

        if item['owner_id'] and item['owner_id'] != UNOWNED_EXTENSION_OWNER_ID:
            return item['owner_id']

        return self._owner_from_extension(item, context, case_id)

    def _owner_from_extension(self, item, context, case_id):
        if item['owner_id'] == UNOWNED_EXTENSION_OWNER_ID:
            accessor = CaseAccessors(context.root_doc['domain'])
            indices = {case_id}
            last_indices = set()
            loop_counter = 0
            # only allow 10 iterations at most in case there are loops
            while indices != last_indices and loop_counter < 10:
                last_indices |= indices
                indices |= set(accessor.get_indexed_case_ids(indices))
                loop_counter += 1

            cases = accessor.get_cases(list(indices))
            cases_with_owners = [
                case for case in cases
                if case.owner_id and case.owner_id != UNOWNED_EXTENSION_OWNER_ID
            ]
            if len(cases_with_owners) != 0:
                # This shouldn't happen in this world, but will feasibly
                # occur depending on our migration path from parent/child ->
                # extension cases. Once a migration path is decided revisit
                # alerting in this case
                return cases_with_owners[0].owner_id

            household_cases = [
                case for case in cases
                if case.type == 'household'
            ]
            assert len(household_cases) == 1
            household_case = household_cases[0]
            subcases = household_case.get_subcases(index_identifier=self.index_identifier)
            cases_with_owners = [
                case for case in subcases
                if case.owner_id and case.owner_id != UNOWNED_EXTENSION_OWNER_ID
            ]
            assert len(cases_with_owners) == 1
            assert cases_with_owners[0].type == 'assignment'

            return cases_with_owners[0].owner_id

        return None

    def __str__(self):
        return "owner_id"


class VillageOwnerId(AWCOwnerId):
    type = TypeProperty('aaa_village_owner_id')
    index_identifier = 'owner_village'

    def __str__(self):
        return "village owner_id"

    def __call__(self, item, context=None):
        case_id = self._case_id_expression(item, context)

        if not case_id:
            return None

        # a village will only be on the case as the owner if
        # its the assignment case so we should verify that
        if item['owner_id'] != UNOWNED_EXTENSION_OWNER_ID:
            accessor = CaseAccessors(context.root_doc['domain'])
            case = accessor.get_case(case_id)
            if case.type == 'assignment':
                # should verify it is a village case (not AWC)
                # via some property to be determined later
                return item['owner_id']

        return self._owner_from_extension(item, context, case_id)


def awc_owner_id(spec, context):
    wrapped = AWCOwnerId.wrap(spec)
    wrapped.configure(
        case_id_expression=ExpressionFactory.from_spec(wrapped.case_id_expression, context)
    )
    return wrapped


def village_owner_id(spec, context):
    wrapped = VillageOwnerId.wrap(spec)
    wrapped.configure(
        case_id_expression=ExpressionFactory.from_spec(wrapped.case_id_expression, context)
    )
    return wrapped
