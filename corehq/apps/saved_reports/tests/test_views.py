from django.test import TestCase
from corehq.apps.saved_reports.models import (
    ReportConfig,
    ReportNotification,
)
from corehq.apps.reports.views import domain_shared_configs


class TestDomainSharedConfigs(TestCase):
    DOMAIN = 'test_domain'
    OWNER_ID = '5'

    def tearDown(self) -> None:
        for c in ReportNotification.by_domain(self.DOMAIN):
            c.delete()

        for r in ReportConfig.by_domain_and_owner(self.DOMAIN, self.OWNER_ID):
            r.delete()

    def test_domain_does_not_have_report_notifications(self):
        self.assertEqual(domain_shared_configs(self.DOMAIN), [])

    def test_domain_has_report_notifications(self):
        config = ReportConfig(domain=self.DOMAIN, owner_id=self.OWNER_ID)
        config.save()
        report = self._create_report(
            domain=self.DOMAIN,
            owner_id=self.OWNER_ID,
            config_ids=[config._id],
        )
        report.clear_caches()
        breakpoint()
        configs = domain_shared_configs(self.DOMAIN)
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]._id, config._id)

    def test_config_used_in_multiple_report_notifications(self):
        pass

    def _create_report(self, domain=None, owner_id=None, config_ids=[]):
        domain = domain or self.domain
        owner_id = owner_id or self.user._id
        report = ReportNotification(domain=domain, owner_id=owner_id, config_ids=config_ids)
        report.save()
        self.addCleanup(report.delete)
        return report


class TestMySavedReportsView(TestCase):

    def test_one_admin_has_report_notifications(self):
        # - Add three ReportConfigs
        # - Add ReportNotification with two of the three ReportConfigs
        # - Verify that shared_saved_reports returns the two ReportConfigs
        pass

    def test_multiple_admins_can_see_shared_reports(self):
        # - Add two admin users (A and B)
        # - Add one ReportConfig for each user
        # - Add one ReportNotification as user A
        # - For user A: shared_saved_reports returns one ReportConfig
        # - For user B: shared_saved_reports returns one ReportConfig
        # - Add one ReportNotification as user B
        # - For user A: shared_saved_reports returns two ReportConfig
        # - For user B: shared_saved_reports returns two ReportConfig
        pass

    def test_non_admin_can_see_only_own_shared_reports(self):
        pass

    def test_admins_can_edit_shared_saved_report(self):
        # - Add two admin users (A and B)
        # - Add one ReportConfig for each user
        # - Add one ReportNotification as user A
        # - As user A: verify ability to edit ReportConfig A
        # - As user A: verify inability to edit ReportConfig B
        # - As user B: verify ability to edit ReportConfig A
        # - As user B: verify ability to edit ReportConfig B
        # - As user B: verify ability to delete ReportConfig A
        pass


def TestScheduledReportsView(TestCase):

    def test_config_choices_also_shows_shared_reports_configs(self):
        pass


class TestAddSavedReportConfigView(TestCase):

    def test_another_admin_cannot_edit_normal_config(self):
        pass

    def test_another_admin_can_edit_shared_config(self):
        pass

    def test_non_admin_cannot_edit_other_shared_configs(self):
        pass
