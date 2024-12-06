from collections import namedtuple

from django.db import models

from corehq.apps.data_analytics.const import (
    DEFAULT_EXPERIENCED_THRESHOLD,
    DEFAULT_PERFORMANCE_THRESHOLD,
    NOT_SET,
)

GIRExportRow = namedtuple('GIRExportRow', [
    'domain',
    'country',
    'sector',
    'subsector',
    'bu',
    'self_service',
    'test',
    'start',
    'device',
    'active_users',
    'pam',
    'wam_current',
    'wam_1_prior',
    'wam_2_prior',
    'active_current',
    'active_1_prior',
    'active_2_prior',
    'using_and_performing',
    'not_performing',
    'inactive_experienced',
    'inactive_not_experienced',
    'not_experienced',
    'not_performing_not_experienced',
    'd1',
    'd2',
    'd3',
    'd4',
    'd5',
    'd6',
    'eligible',
    'experienced_threshold',
    'performance_threshold',
])


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

    wam = models.BooleanField(null=True, default=NOT_SET)
    pam = models.BooleanField(null=True, default=NOT_SET)

    use_threshold = models.PositiveSmallIntegerField(default=DEFAULT_PERFORMANCE_THRESHOLD)
    experienced_threshold = models.PositiveSmallIntegerField(default=DEFAULT_EXPERIENCED_THRESHOLD)

    # the last time the MALT was generated for this domain and month
    last_run_date = models.DateTimeField(default=None, blank=True, null=True)

    class Meta(object):
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

    self_service = models.BooleanField(null=True, default=NOT_SET)
    test_domain = models.BooleanField(null=True, default=NOT_SET)
    start_date = models.DateField()
    device_id = models.TextField(blank=True, null=True)
    pam = models.BooleanField(null=True, default=NOT_SET)

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
    eligible_forms = models.PositiveIntegerField()
    performance_threshold = models.PositiveIntegerField(null=True)
    experienced_threshold = models.PositiveIntegerField(null=True)

    class Meta(object):
        unique_together = ('month', 'domain_name')

    def export_row(self, past_months):
        last_month = past_months[0] if past_months else None
        two_months_ago = past_months[1] if len(past_months) > 1 else None
        wams_current = self.wams_current
        wams_1_prior = last_month.wams_current if last_month else 0
        wams_2_prior = two_months_ago.wams_current if two_months_ago else 0
        return GIRExportRow(
            domain=self.domain_name,
            country=self.country,
            sector=self.sector,
            subsector=self.subsector,
            bu=self.bu,
            self_service=self.self_service,
            test=self.test_domain,
            start=self.start_date,
            device=self.device_id,
            active_users=self.active_users,
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
            d6=self.active_in_span,
            eligible=self.eligible_forms,
            experienced_threshold=self.experienced_threshold or DEFAULT_EXPERIENCED_THRESHOLD,
            performance_threshold=self.performance_threshold or DEFAULT_PERFORMANCE_THRESHOLD,
        )


class DomainMetrics(models.Model):

    domain = models.TextField(unique=True, db_index=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    has_project_icon = models.BooleanField()
    has_security_settings = models.BooleanField()
    is_active = models.BooleanField()
    is_first_domain_for_creating_user = models.BooleanField()

    lookup_tables = models.IntegerField()
    repeaters = models.IntegerField()
    ucrs = models.IntegerField()

    # App Metrics
    apps = models.IntegerField()
    apps_with_icon = models.IntegerField()
    apps_with_multiple_languages = models.IntegerField()

    # User Metrics
    mobile_workers = models.IntegerField()
    web_users = models.IntegerField()

    active_mobile_workers = models.IntegerField()
    active_mobile_workers_in_last_365_days = models.IntegerField()
    case_sharing_groups = models.IntegerField()
    case_sharing_locations = models.IntegerField()
    has_custom_roles = models.BooleanField()
    has_locations = models.BooleanField()
    location_restricted_users = models.IntegerField()
    users_with_submission = models.IntegerField()

    # Case Metrics
    cases = models.IntegerField()

    active_cases = models.IntegerField()
    cases_modified_in_last_30_days = models.IntegerField()
    cases_modified_in_last_60_days = models.IntegerField()
    cases_modified_in_last_90_days = models.IntegerField()
    inactive_cases = models.IntegerField()
    usercases_modified_in_last_30_days = models.IntegerField()

    # Form Metrics
    forms = models.IntegerField()
    forms_submitted_in_last_30_days = models.IntegerField()
    forms_submitted_in_last_60_days = models.IntegerField()
    forms_submitted_in_last_90_days = models.IntegerField()

    first_form_submission = models.DateTimeField(null=True)
    most_recent_form_submission = models.DateTimeField(null=True)
    three_hundredth_form_submission = models.DateTimeField(null=True)

    # SMS Metrics
    total_sms = models.IntegerField()
    sms_in_last_30_days = models.IntegerField()
    sms_in_last_60_days = models.IntegerField()
    sms_in_last_90_days = models.IntegerField()

    incoming_sms = models.IntegerField()
    incoming_sms_in_last_30_days = models.IntegerField()
    incoming_sms_in_last_60_days = models.IntegerField()
    incoming_sms_in_last_90_days = models.IntegerField()

    outgoing_sms = models.IntegerField()
    outgoing_sms_in_last_30_days = models.IntegerField()
    outgoing_sms_in_last_60_days = models.IntegerField()
    outgoing_sms_in_last_90_days = models.IntegerField()

    telerivet_backends = models.IntegerField()

    # Export Metrics
    case_exports = models.IntegerField()
    custom_exports = models.IntegerField()
    deid_exports = models.IntegerField()
    saved_exports = models.IntegerField()

    # Calculated properties
    @property
    def has_app(self):
        return bool(self.apps)

    @property
    def has_used_sms(self):
        return bool(self.total_sms)

    @property
    def has_used_sms_in_last_30_days(self):
        return bool(self.sms_in_last_30_days)
