from __future__ import absolute_import
from casexml.apps.case.util import get_datetime_case_property_changed
from custom.enikshay.const import (
    FIRST_PRESCRIPTION_VOUCHER_REDEEMED_DATE,
    FIRST_PRESCRIPTION_VOUCHER_REDEEMED,
    ENROLLED_IN_PRIVATE,
    REAL_DATASET_PROPERTY_VALUE,
)


class VoucherRedeemedDateSetter(object):
    """Sets the bets_first_prescription_voucher_redeemed_date property for use by
    the BETSDiagnosisAndNotificationRepeater

    """

    def __init__(self, domain, person, episode):
        self.domain = domain
        self.person = person
        self.episode = episode

    def update_json(self):
        if not self.should_update:
            return {}

        redeemed_datetime = get_datetime_case_property_changed(
            self.episode, FIRST_PRESCRIPTION_VOUCHER_REDEEMED, 'true',
        )
        if redeemed_datetime is not None:
            return {
                FIRST_PRESCRIPTION_VOUCHER_REDEEMED_DATE: str(redeemed_datetime.date())
            }
        else:
            return {}

    @property
    def should_update(self):
        if self.episode.get_case_property(FIRST_PRESCRIPTION_VOUCHER_REDEEMED_DATE) is not None:
            return False

        if self.episode.get_case_property(ENROLLED_IN_PRIVATE) != 'true':
            return False

        if self.person.get_case_property('dataset') != REAL_DATASET_PROPERTY_VALUE:
            return False

        return True
