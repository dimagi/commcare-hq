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


DOMAIN_METRICS_TO_PROPERTIES_MAP = {
    'active_cases': 'cp_n_active_cases',
    'active_mobile_workers': 'cp_n_active_cc_users',
    'active_mobile_workers_in_last_365_days': 'cp_n_active_cc_users_365_days',
    'apps': 'cp_n_apps',
    'apps_with_icon': 'cp_n_apps_with_icon',
    'apps_with_multiple_languages': 'cp_n_apps_with_multi_lang',
    'case_exports': 'cp_n_case_exports',
    'case_sharing_groups': 'cp_n_case_sharing_groups',
    'case_sharing_locations': 'cp_n_case_sharing_olevels',
    'cases': 'cp_n_cases',
    'cases_modified_in_last_30_days': 'cp_n_30_day_cases',
    'cases_modified_in_last_60_days': 'cp_n_60_day_cases',
    'cases_modified_in_last_90_days': 'cp_n_90_day_cases',
    'custom_exports': 'cp_n_saved_custom_exports',
    'custom_roles': 'cp_n_custom_roles',
    'deid_exports': 'cp_n_deid_exports',
    'first_form_submission': 'cp_first_form',
    'forms': 'cp_n_forms',
    'forms_submitted_in_last_30_days': 'cp_n_forms_30_d',
    'forms_submitted_in_last_60_days': 'cp_n_forms_60_d',
    'forms_submitted_in_last_90_days': 'cp_n_forms_90_d',
    'has_app': 'cp_has_app',  # read-only property
    'has_project_icon': 'cp_has_project_icon',
    'has_used_sms': 'cp_sms_ever',  # read-only property
    'has_used_sms_in_last_30_days': 'cp_sms_30_d',  # read-only property
    'has_users_with_location': 'cp_using_locations',
    'has_security_settings': 'cp_use_domain_security',
    'inactive_cases': 'cp_n_inactive_cases',
    'incoming_sms': 'cp_n_in_sms',
    'incoming_sms_in_last_30_days': 'cp_n_sms_in_30_d',
    'incoming_sms_in_last_60_days': 'cp_n_sms_in_60_d',
    'incoming_sms_in_last_90_days': 'cp_n_sms_in_90_d',
    'is_active': 'cp_is_active',
    'is_first_domain_for_creating_user': 'cp_first_domain_for_user',
    'last_modified': 'cp_last_updated',
    'location_restricted_roles': 'cp_n_loc_restricted_roles',
    'lookup_tables': 'cp_n_lookup_tables',
    'mobile_workers': 'cp_n_cc_users',
    'most_recent_form_submission': 'cp_last_form',
    'outgoing_sms': 'cp_n_out_sms',
    'outgoing_sms_in_last_30_days': 'cp_n_sms_out_30_d',
    'outgoing_sms_in_last_60_days': 'cp_n_sms_out_60_d',
    'outgoing_sms_in_last_90_days': 'cp_n_sms_out_90_d',
    'repeaters': 'cp_n_repeaters',
    'report_builder_reports': 'cp_n_rb_reports',
    'saved_exports': 'cp_n_saved_exports',
    'sms_in_last_30_days': 'cp_n_sms_30_d',
    'sms_in_last_60_days': 'cp_n_sms_60_d',
    'sms_in_last_90_days': 'cp_n_sms_90_d',
    'telerivet_backends': 'cp_n_trivet_backends',
    'three_hundredth_form_submission': 'cp_300th_form',
    'total_sms': 'cp_n_sms_ever',
    'ucrs': 'cp_n_ucr_reports',
    'usercases_modified_in_last_30_days': 'cp_n_30_day_user_cases',
    'users_with_submission': 'cp_n_users_submitted_form',
    'web_users': 'cp_n_web_users',
}


class DomainMetrics(models.Model):

    domain = models.TextField(unique=True, db_index=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    is_active = models.BooleanField()
    is_first_domain_for_creating_user = models.BooleanField()
    has_project_icon = models.BooleanField()
    has_security_settings = models.BooleanField()
    has_users_with_location = models.BooleanField()

    lookup_tables = models.IntegerField()
    repeaters = models.IntegerField()
    report_builder_reports = models.IntegerField()
    ucrs = models.IntegerField()

    # App Metrics
    apps = models.IntegerField()
    apps_with_icon = models.IntegerField()
    apps_with_multiple_languages = models.IntegerField()

    # User Metrics
    mobile_workers = models.IntegerField()
    web_users = models.IntegerField()

    users_with_submission = models.IntegerField()
    active_mobile_workers = models.IntegerField()
    active_mobile_workers_in_last_365_days = models.IntegerField()
    case_sharing_groups = models.IntegerField()
    case_sharing_locations = models.IntegerField()
    custom_roles = models.IntegerField()
    location_restricted_roles = models.IntegerField()

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

    def to_calculated_properties(self):
        return {
            calced_props_key: getattr(self, metrics_attr, None)
            for metrics_attr, calced_props_key in DOMAIN_METRICS_TO_PROPERTIES_MAP.items()
        }
