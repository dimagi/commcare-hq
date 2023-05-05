from corehq.apps.api.resources import v0_5
from corehq.apps.auditcare.models import NavigationEventAudit
from django.test import TestCase

from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo


class DomainNavigationEventAudits:
    def __init__(self, domain: str, project_time_zone: ZoneInfo):
        self.domain = domain
        self.timezone = project_time_zone
        self.logs = {}

    def add_log(self, user: str, date_time: datetime):
        self.logs.setdefault(user, set()).add(date_time)

    def set_expected_query_results(self, expected_result: list[dict]):
        self.expected_result = expected_result

    def create(self):
        for user, times in self.logs.items():
            for time in times:
                NavigationEventAudit.objects.create(domain=self.domain, user=user, event_date=time)


class testNavigationEventAuditResource(TestCase):
    resource = v0_5.NavigationEventAuditResource

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain1_audits = DomainNavigationEventAudits("domain1", ZoneInfo('America/Los_Angeles'))
        cls.domain2_audits = DomainNavigationEventAudits("domain2", ZoneInfo('America/Los_Angeles'))

        cls.user1 = "emapson@dimagi.com"
        cls.user2 = "jtang@dimagi.com"

        for single_datetime in cls._daterange(datetime(2023, 5, 2, 0), datetime(2023, 5, 2, 23)):
            cls.domain1_audits.add_log(cls.user1, single_datetime)
            cls.domain1_audits.add_log(cls.user1, single_datetime)
            cls.domain1_audits.add_log(cls.user2, single_datetime)

        for single_datetime in cls._daterange(datetime(2023, 6, 1, 0), datetime(2023, 5, 31, 23)):
            cls.domain2_audits.add_log(cls.user1, single_datetime)
            cls.domain2_audits.add_log(cls.user2, single_datetime)

        cls.domain1_audits.create()
        cls.domain2_audits.create()

        cls.domain1_audits.set_expected_query_results([
            {
                'user': cls.user1,
                'local_date': date(2023, 5, 1),
                'UTC_first_action_time': datetime(2023, 5, 2, 0, tzinfo=ZoneInfo("UTC")),
                'UTC_last_action_time': datetime(2023, 5, 2, 6, tzinfo=ZoneInfo("UTC"))
            },
            {
                'user': cls.user2,
                'local_date': date(2023, 5, 1),
                'UTC_first_action_time': datetime(2023, 5, 2, 0, tzinfo=ZoneInfo("UTC")),
                'UTC_last_action_time': datetime(2023, 5, 2, 6, tzinfo=ZoneInfo("UTC"))
            },
            {
                'user': cls.user1,
                'local_date': date(2023, 5, 2),
                'UTC_first_action_time': datetime(2023, 5, 2, 7, tzinfo=ZoneInfo("UTC")),
                'UTC_last_action_time': datetime(2023, 5, 2, 23, tzinfo=ZoneInfo("UTC"))
            },
            {
                'user': cls.user2,
                'local_date': date(2023, 5, 2),
                'UTC_first_action_time': datetime(2023, 5, 2, 7, tzinfo=ZoneInfo("UTC")),
                'UTC_last_action_time': datetime(2023, 5, 2, 23, tzinfo=ZoneInfo("UTC"))
            }
        ])

    def _daterange(start_datetime, end_datetime):
        for n in range(int((end_datetime - start_datetime).total_seconds() // 3600) + 1):
            yield start_datetime + timedelta(hours=n)
