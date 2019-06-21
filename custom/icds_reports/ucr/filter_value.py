from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.reports.util import get_INFilter_element_bindparam
from corehq.apps.userreports.reports.filters.values import ChoiceListFilterValue
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


class VillageFilterValue(ChoiceListFilterValue):
    ALLOWED_TYPES = ('village_choice_list', )

    def __init__(self, filter, value):
        super(VillageFilterValue, self).__init__(filter, value)

    @property
    def is_null(self):
        if super(VillageFilterValue, self).is_null is True:
            return True
        # If there are no case ids that belong to the user, then nothing
        # will be bound to the parameter in the future, and it would error
        return len(self._get_case_ids()) == 0

    def _get_case_ids(self):
        asha_location_ids = [choice.value for choice in self.value]
        accessor = CaseAccessors('icds-cas')  # figure out how to get the domain here
        return accessor.get_case_ids_by_owners(asha_location_ids)

    def to_sql_values(self):
        if self.show_all or self.is_null:
            return {}
        case_ids = self._get_case_ids()
        values = {
            get_INFilter_element_bindparam(self.filter['slug'], i): val.value
            for i, val in enumerate(case_ids)
        }
        return values
