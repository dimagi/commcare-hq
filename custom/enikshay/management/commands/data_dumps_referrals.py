from __future__ import absolute_import
from __future__ import print_function

from corehq.apps.users.models import CommCareUser

from custom.enikshay.case_utils import (
    CASE_TYPE_REFERRAL,
    get_person_case_from_referral,
)
from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE,
)
from custom.enikshay.management.commands.base_data_dump import BaseDataDump

DOMAIN = "enikshay"


class Command(BaseDataDump):
    """
    13. Referral cases
    https://docs.google.com/spreadsheets/d/1OPp0oFlizDnIyrn7Eiv11vUp8IBmc73hES7qqT-mKKA/edit#gid=357905283
    """
    TASK_NAME = "13_referrals"
    INPUT_FILE_NAME = "data_dumps_referrals.csv"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_REFERRAL

    def get_case_ids_query(self, case_type):
        """
        All open and closed referral cases
        1) whose host/host = a person case (open or closed)
        with person.dataset = 'real' and
        person.enrolled_in_private != 'true'
        """
        return self.case_search_instance.case_type(case_type)

    def include_case_in_dump(self, referral):
        person = self.get_person(referral)
        return (
            person and
            person.get_case_property('dataset') == 'real' and
            person.get_case_property(ENROLLED_IN_PRIVATE) != 'true'
        )

    def get_person(self, referral):
        if 'person' not in self.context:
            self.context['person'] = get_person_case_from_referral(DOMAIN, referral.case_id)
        return self.context['person']

    def get_case_reference_value(self, case_reference, referral, calculation):
        if case_reference == 'person':
            return self.get_person(referral).get_case_property(calculation)
        return Exception("unknown case reference %s" % case_reference)

    def get_custom_value(self, column_name, referral):
        if column_name == "Date of Creation of Referral Case":
            return referral.opened_on
        elif column_name == "Created by Username":
            user_id = None
            try:
                user_id = referral.opened_by
                return CommCareUser.get_by_user_id(user_id, DOMAIN).username
            except Exception as e:
                return Exception("Could not get username. case opened by %s, %s" % (user_id, e))
        elif column_name == "Created by User ID":
            return referral.opened_by
        return Exception("unknown custom column %s" % column_name)
