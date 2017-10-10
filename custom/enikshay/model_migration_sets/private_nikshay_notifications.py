from casexml.apps.case.util import get_datetime_case_property_changed
from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE,
    REAL_DATASET_PROPERTY_VALUE,
)


class PrivateNikshayNotifiedDateSetter(object):
    """Sets the date_private_nikshay_notification property for use in reports
    """

    def __init__(self, domain, person, episode):
        self.domain = domain
        self.person = person
        self.episode = episode

    def update_json(self):
        if not self.should_update:
            return {}

        registered_datetime = get_datetime_case_property_changed(
            self.episode, 'private_nikshay_registered', 'true',
        )
        if registered_datetime is not None:
            return {
                'date_private_nikshay_notification': str(registered_datetime.date())
            }
        else:
            return {}

    @property
    def should_update(self):
        if self.episode.get_case_property('date_private_nikshay_notification') is not None:
            return False

        if self.episode.get_case_property('private_nikshay_registered') != 'true':
            return False

        if self.episode.get_case_property(ENROLLED_IN_PRIVATE) != 'true':
            return False

        if self.person.get_case_property('dataset') != REAL_DATASET_PROPERTY_VALUE:
            return False

        return True
