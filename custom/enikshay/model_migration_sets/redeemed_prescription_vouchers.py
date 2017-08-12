from casexml.apps.case.util import get_datetime_case_property_changed


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
            self.episode, 'bets_first_prescription_voucher_redeemed', 'true',
        )
        if redeemed_datetime is not None:
            return {
                'bets_first_prescription_voucher_redeemed_date': str(redeemed_datetime.date())
            }
        else:
            return {}

    @property
    def should_update(self):
        if self.episode.get_case_property('bets_first_prescription_voucher_redeemed_date') is not None:
            return False

        if self.episode.get_case_property('enrolled_in_private') != 'true':
            return False

        if self.person.get_case_property('dataset') != 'real':
            return False

        return True
