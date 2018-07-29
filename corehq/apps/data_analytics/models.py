from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple

from django.db import models

from corehq.apps.data_analytics.const import NOT_SET, DEFAULT_EXPERIENCED_THRESHOLD, DEFAULT_PERFORMANCE_THRESHOLD


GIRExportRow = namedtuple('GIRExportRow',
                          'domain country sector subsector bu self_service test start device active_users wam '
                          'pam wam_current wam_1_prior wam_2_prior active_current active_1_prior active_2_prior '
                          'using_and_performing not_performing inactive_experienced inactive_not_experienced '
                          'not_experienced not_performing_not_experienced d1 d2 d3 d4 d5 d6 eligible '
                          'experienced_threshold performance_threshold ')


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

    wam = models.NullBooleanField(default=NOT_SET)
    pam = models.NullBooleanField(default=NOT_SET)

    use_threshold = models.PositiveSmallIntegerField(default=15)
    experienced_threshold = models.PositiveSmallIntegerField(default=3)

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
    eligible_forms = models.PositiveIntegerField()
    performance_threshold = models.PositiveIntegerField(null=True)
    experienced_threshold = models.PositiveIntegerField(null=True)

    class Meta(object):
        unique_together = ('month', 'domain_name')

    def export_row(self, past_months):
        last_month = past_months[0] if past_months else None
        two_months_ago = past_months[1] if len(past_months) > 1 else None
        wams_current = self.wams_current if self.wam else 0
        wams_1_prior = last_month.wams_current if last_month and self.wam else 0
        wams_2_prior = two_months_ago.wams_current if two_months_ago and self.wam else 0
        return GIRExportRow(domain=self.domain_name,
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
                            d6=self.active_in_span,
                            eligible=self.eligible_forms,
                            experienced_threshold=self.experienced_threshold or DEFAULT_EXPERIENCED_THRESHOLD,
                            performance_threshold=self.performance_threshold or DEFAULT_PERFORMANCE_THRESHOLD)
