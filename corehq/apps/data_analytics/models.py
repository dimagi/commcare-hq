from collections import namedtuple

from django.db import models

from corehq.apps.app_manager.const import AMPLIFIES_YES, AMPLIFIES_NO, AMPLIFIES_NOT_SET

YES = True
NO = False
NOT_SET = None
AMPLIFY_COUCH_TO_SQL_MAP = {
    AMPLIFIES_YES: YES,
    AMPLIFIES_NO: NO,
    AMPLIFIES_NOT_SET: NOT_SET
}
TEST_COUCH_TO_SQL_MAP = {
    "true": YES,
    "false": NO,
    "none": NOT_SET
}

BU_MAPPING = {
    "AF": "DSI",
    "AO": "DSA",
    "BD": "DSI",
    "BZ": "DLAC",
    "BJ": "DWA",
    "BR": "DLAC",
    "BF": "DWA",
    "BI": "DSA",
    "CM": "DWA",
    "CA": "INC",
    "TD": "DWA",
    "CN": "NA",
    "CO": "DLAC",
    "DO": "DLAC",
    "EG": "INC",
    "ET": "DSA",
    "FR": "INC",
    "GM": "DWA",
    "GH": "DWA",
    "GD": "DLAC",
    "GT": "DLAC",
    "GN": "DWA",
    "HT": "DLAC",
    "HN": "DLAC",
    "IN": "DSI",
    "ID": "DSI",
    "IQ": "INC",
    "JO": "INC",
    "KE": "DSA",
    "LA": "DSI",
    "LS": "DSA",
    "LR": "DWA",
    "MG": "DSA",
    "MW": "DSA",
    "MY": "DSI",
    "ML": "DWA",
    "MX": "DLAC",
    "MZ": "DMOZ",
    "MM": "DSI",
    "NA": "DSA",
    "NP": "DSI",
    "NI": "DLAC",
    "NE": "DWA",
    "NG": "DWA",
    "PK": "DSI",
    "PE": "DLAC",
    "PH": "DSI",
    "RW": "DSA",
    "SN": "DWA",
    "SL": "DWA",
    "ZA": "DSA",
    "SS": "DSA",
    "ES": "INC",
    "LK": "DSI",
    "SY": "INC",
    "TZ": "DSA",
    "TH": "DSI",
    "TL": "DSI",
    "TG": "DWA",
    "TR": "INC",
    "UG": "DSA",
    "GB": "INC",
    "US": "INC",
    "VN": "DSI",
    "ZM": "DSA",
    "ZW": "DSA",
}

GIR_FIELDS = [
    "Project Space",
    "Country",
    "Sector",
    "Subsector",
    "Business Unit",
    "Self Service",
    "Test Domain",
    "Domain Start Date",
    "Dominant Device Type",
    "Active Users",
    "Eligible for WAMs",
    "Eligible for PAMs",
    "WAMs current month",
    "WAMs 1 month prior",
    "WAMs 2 months prior",
    "Active Users current month",
    "Active Users 1 month prior",
    "Active Users 2 months prior",
    "Using and Performing",
    "Not Performing",
    "Inactive and Experienced",
    "Inactive and Not Experienced",
    "Not Experienced",
    "Not Performing and Not Experienced",
    "D1 All Users Ever Active",
    "D2 All Possibly Exp Users",
    "D3 All Ever Exp Users",
    "D4 All Experienced + Active Users",
    "D5 All Active Users",
    "D6 All Active Users Current + Prior 2 Mos",
]

girrow = namedtuple('girrow',
                    'domain country sector subsector bu self_service test start device active_users wam '
                    'pam wam_current wam_1_prior wam_2_prior active_current active_1_prior active_2_prior '
                    'using_and_performing not_performing inactive_experienced inactive_not_experienced '
                    'not_experienced not_performing_not_experienced d1 d2 d3 d4 d5 d6')


class MALTRow(models.Model):
    """
        Specifies a row for 'Monthly Aggregate Lite Table (MALT)'
        See https://docs.google.com/document/d/1QQ3tzFPs6TWiPiah6YUBCrFILKih6OcJV7444i50o1U/edit
    """
    month = models.DateField(db_index=True)

    # Using TextField instead of CharField, because...
    # postgres doesn't differentiate between Char/Text and there is no hard max-length limit
    user_id = models.TextField()
    username = models.TextField()
    email = models.EmailField()
    user_type = models.TextField()

    domain_name = models.TextField(db_index=True)
    num_of_forms = models.PositiveIntegerField()
    app_id = models.TextField()
    device_id = models.TextField(blank=True, null=True)
    is_app_deleted = models.BooleanField(default=False)

    YES = True  # equivalent to app_manager.const.AMPLIFIES_YES
    NO = False  # equivalent to app_manager.const.AMPLIFIES_NO
    NOT_SET = None  # equivalent to app_manager.const.AMPLIFIES_NOT_SET
    wam = models.NullBooleanField(default=NOT_SET)
    pam = models.NullBooleanField(default=NOT_SET)

    use_threshold = models.PositiveSmallIntegerField(default=15)
    experienced_threshold = models.PositiveSmallIntegerField(default=3)

    class Meta:
        unique_together = ('month', 'domain_name', 'user_id', 'app_id', 'device_id')

    @classmethod
    def get_unique_fields(cls):
        return list(cls._meta.unique_together[0])


class GIRRow(models.Model):

    month = models.DateField(db_index=True)

    domain_name = models.TextField()
    country = models.TextField(blank=True, null=True)
    sector = models.TextField(blank=True, null=True)
    subsector = models.TextField(blank=True, null=True)
    bu = models.TextField(blank=True, null=True)

    self_service = models.NullBooleanField(default=NOT_SET)
    test_domain = models.NullBooleanField(default=NOT_SET)
    start_date = models.DateField()
    device_id = models.TextField(blank=True, null=True)
    wam = models.NullBooleanField(default=NOT_SET)
    pam = models.NullBooleanField(default=NOT_SET)

    wams_current = models.PositiveIntegerField()
    active_users = models.PositiveIntegerField()
    using_and_performing = models.PositiveIntegerField()
    not_performing = models.PositiveIntegerField()
    inactive_experienced = models.PositiveIntegerField()
    inactive_not_experienced = models.PositiveIntegerField()
    not_experienced = models.PositiveIntegerField()
    not_performing_not_experienced = models.PositiveIntegerField()
    active_ever = models.PositiveIntegerField()
    possibly_exp = models.PositiveIntegerField()
    ever_exp = models.PositiveIntegerField()
    exp_and_active_ever = models.PositiveIntegerField()
    active_in_span = models.PositiveIntegerField()

    @property
    def export_row(self):
        past_months = GIRRow.objects.filter(domain_name=self.domain_name, month__lt=self.month).order_by('-month')
        last_month = past_months[0] if past_months else None
        two_months_ago = past_months[1] if len(past_months) > 1 else None
        wams_current = self.wams_current if self.wam else 0
        wams_1_prior = last_month.wams_current if last_month and self.wam else 0
        wams_2_prior = two_months_ago.wams_current if two_months_ago and self.wam else 0
        return girrow(domain=self.domain_name,
                      country=self.country,
                      sector=self.sector,
                      subsector=self.subsector,
                      bu=self.bu,
                      self_service=self.self_service,
                      test=self.test_domain,
                      start=self.start_date,
                      device=self.device_id,
                      active_users=self.active_users,
                      wam=self.wam,
                      pam=self.pam,
                      wam_current=wams_current,
                      wam_1_prior=wams_1_prior,
                      wam_2_prior=wams_2_prior,
                      active_current=self.active_users,
                      active_1_prior=last_month.active_users if last_month else 0,
                      active_2_prior=two_months_ago.active_users if two_months_ago else 0,
                      using_and_performing=self.using_and_performing,
                      not_performing=self.not_performing,
                      inactive_experienced=self.inactive_experienced,
                      inactive_not_experienced=self.inactive_not_experienced,
                      not_experienced=self.not_experienced,
                      not_performing_not_experienced=self.not_performing_not_experienced,
                      d1=self.active_ever,
                      d2=self.possibly_exp,
                      d3=self.ever_exp,
                      d4=self.exp_and_active_ever,
                      d5=self.active_users,
                      d6=self.active_in_span)
