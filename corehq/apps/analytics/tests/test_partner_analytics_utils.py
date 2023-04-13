import calendar
import datetime
from unittest import mock

from django.test import SimpleTestCase, TestCase

from dimagi.utils.dates import get_start_and_end_dates_of_month

from corehq.apps.accounting.models import DomainUserHistory
from corehq.apps.analytics.models import (
    PartnerAnalyticsContact,
    PartnerAnalyticsDataPoint,
    PartnerAnalyticsReport,
)
from corehq.apps.analytics.utils.partner_analytics import (
    ACCESS_ODATA,
    NUMBER_OF_MOBILE_WORKERS,
    NUMBER_OF_SUBMISSIONS,
    NUMBER_OF_WEB_USERS,
    _get_csv_value,
    generate_monthly_mobile_worker_statistics,
    generate_monthly_submissions_statistics,
    generate_monthly_web_user_statistics,
    get_csv_details_for_partner,
    get_number_of_mobile_workers,
    get_number_of_submissions,
    get_number_of_web_users,
    send_partner_emails,
    track_partner_access,
)
from corehq.apps.domain.models import Domain
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.users.models import Invitation, WebUser
from corehq.form_processor.tests.utils import create_form_for_test


def _get_fake_number_of_mobile_workers(domain, _year, _month):
    return {
        'test-001': 10,
        'test-002': 20,
        'test-003': 30,
    }[domain]


def _get_fake_number_of_web_users(domain, _year, _month):
    return {
        'test-001': 11,
        'test-002': 21,
        'test-003': 31,
    }[domain]


def _get_fake_number_of_submissions(domain, _year, _month):
    return {
        'test-001': 11,
        'test-002': 22,
        'test-003': 33,
    }[domain]


@es_test(requires=[user_adapter, form_adapter], setup_class=True)
class TestPartnerAnalyticsDataUtils(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.date_start, cls.date_end = get_start_and_end_dates_of_month(2021, 11)
        cls.domain = Domain.get_or_create_with_name('test-partner-analytics', is_active=True)
        cls.addClassCleanup(cls.domain.delete)

        # Data for Mobile Workers Tests
        DomainUserHistory.objects.create(
            domain=cls.domain.name,
            record_date=cls.date_end,
            num_users=3
        )
        DomainUserHistory.objects.create(
            domain=cls.domain.name,
            record_date=cls.date_start - datetime.timedelta(days=1),
            num_users=6
        )
        DomainUserHistory.objects.create(
            domain=cls.domain.name,
            record_date=cls.date_end + datetime.timedelta(days=1),
            num_users=9
        )

        # Data for Web Users tests
        cls.users = [
            WebUser.create(
                cls.domain.name, 'user1@partner.org', 'testpwd', None, None,
                date=cls.date_start + datetime.timedelta(days=5)
            ),
            WebUser.create(
                cls.domain.name, 'user2@partner.org', 'testpwd', None, None,
                date=cls.date_start - datetime.timedelta(days=1)
            ),
            WebUser.create(
                cls.domain.name, 'user3@partner.org', 'testpwd', None, None,
                date=cls.date_end + datetime.timedelta(days=1)
            ),
            WebUser.create(
                cls.domain.name, 'user4@partner.org', 'testpwd', None, None,
                date=cls.date_start + datetime.timedelta(days=6)
            ),
        ]

        def delete_user(user):
            from couchdbkit import ResourceNotFound
            try:
                user.delete(cls.domain.name, None)
            except ResourceNotFound:
                pass
        for user in cls.users:
            user_adapter.index(user, refresh=True)
            cls.addClassCleanup(delete_user, user)

        invitations = [
            Invitation.objects.create(
                domain=cls.domain.name,
                email='user5@partner.org',
                invited_by='user1@partner.org',
                invited_on=cls.date_start + datetime.timedelta(days=5),
            ),
            Invitation.objects.create(
                domain=cls.domain.name,
                email='user6@partner.org',
                invited_by='user1@partner.org',
                invited_on=cls.date_start - datetime.timedelta(days=1),
            ),
            Invitation.objects.create(
                domain=cls.domain.name,
                email='user7@partner.org',
                invited_by='user1@partner.org',
                invited_on=cls.date_end + datetime.timedelta(days=1),
            ),
        ]
        for invitation in invitations:
            invitation.is_accepted = True
            invitation.save()

        # Data for forms tests
        forms = [
            create_form_for_test(
                cls.domain.name,
                received_on=cls.date_start - datetime.timedelta(days=1)
            ),
            create_form_for_test(
                cls.domain.name,
                received_on=cls.date_end + datetime.timedelta(days=1)
            ),
            create_form_for_test(
                cls.domain.name,
                received_on=cls.date_start + datetime.timedelta(days=3)
            ),
            create_form_for_test(
                cls.domain.name,
                received_on=cls.date_start + datetime.timedelta(days=12)
            ),
        ]
        for form in forms:
            form_adapter.index(form, refresh=True)

    def test_get_number_of_mobile_workers(self):
        self.assertEqual(
            get_number_of_mobile_workers(
                self.domain.name, self.date_start.year, self.date_start.month
            ),
            3
        )

    def test_get_number_of_web_users(self):
        self.assertEqual(
            get_number_of_web_users(
                self.domain.name, self.date_start.year, self.date_start.month
            ),
            4
        )

    def test_get_number_of_submissions(self):
        self.assertEqual(
            get_number_of_submissions(
                self.domain.name, self.date_start.year, self.date_start.month
            ),
            2
        )


class TestPartnerAnalyticsReportUtils(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        today = datetime.datetime.utcnow()
        cls.month = today.month
        cls.year = today.year

        cls.contact = PartnerAnalyticsContact.objects.create(
            organization_name="Helping Earth",
            emails=["test1@helpingearth.org", "test2@helpingearth.org"],
        )
        domains = ['test-001', 'test-002', 'test-003']

        PartnerAnalyticsReport.objects.create(
            contact=cls.contact,
            title="Number of Mobile Workers",
            data_slug=NUMBER_OF_MOBILE_WORKERS,
            domains=domains,
        )

        PartnerAnalyticsReport.objects.create(
            contact=cls.contact,
            title="Number of Web Users",
            data_slug=NUMBER_OF_WEB_USERS,
            domains=domains,
        )

        PartnerAnalyticsReport.objects.create(
            contact=cls.contact,
            title="Number of Submissions",
            data_slug=NUMBER_OF_SUBMISSIONS,
            domains=domains,
        )

        PartnerAnalyticsReport.objects.create(
            contact=cls.contact,
            title="OData Access",
            data_slug=ACCESS_ODATA,
            domains=domains,
        )

    def tearDown(self):
        PartnerAnalyticsDataPoint.objects.all().delete()
        super().tearDown()

    @classmethod
    def tearDownClass(cls):
        PartnerAnalyticsReport.objects.all().delete()
        super().tearDownClass()

    @mock.patch(
        'corehq.apps.analytics.utils.partner_analytics.get_number_of_mobile_workers',
        _get_fake_number_of_mobile_workers
    )
    def test_generate_monthly_mobile_worker_statistics(self):
        generate_monthly_mobile_worker_statistics(self.year, self.month)
        data_points = PartnerAnalyticsDataPoint.objects.filter(
            slug=NUMBER_OF_MOBILE_WORKERS
        )
        self.assertEqual(data_points.count(), 3)
        self.assertEqual(
            sum(data_points.values_list('value', flat=True)),
            60
        )

    @mock.patch(
        'corehq.apps.analytics.utils.partner_analytics.get_number_of_web_users',
        _get_fake_number_of_web_users
    )
    def test_generate_monthly_web_user_statistics(self):
        generate_monthly_web_user_statistics(self.year, self.month)
        data_points = PartnerAnalyticsDataPoint.objects.filter(
            slug=NUMBER_OF_WEB_USERS
        )
        self.assertEqual(data_points.count(), 3)
        self.assertEqual(
            sum(data_points.values_list('value', flat=True)),
            63
        )

    @mock.patch(
        'corehq.apps.analytics.utils.partner_analytics.get_number_of_submissions',
        _get_fake_number_of_submissions
    )
    def test_generate_monthly_submissions_statistics(self):
        generate_monthly_submissions_statistics(self.year, self.month)
        data_points = PartnerAnalyticsDataPoint.objects.filter(
            slug=NUMBER_OF_SUBMISSIONS
        )
        self.assertEqual(data_points.count(), 3)
        self.assertEqual(
            sum(data_points.values_list('value', flat=True)),
            66
        )

    def test_track_partner_access(self):
        track_partner_access(ACCESS_ODATA, 'test-001')
        track_partner_access(ACCESS_ODATA, 'test-001')
        track_partner_access(ACCESS_ODATA, 'test-001')
        data_points = PartnerAnalyticsDataPoint.objects.filter(
            slug=ACCESS_ODATA
        )
        self.assertEqual(data_points.count(), 1)
        self.assertEqual(
            data_points.first().value,
            3
        )

    def test_track_partner_access_no_match(self):
        track_partner_access(ACCESS_ODATA, 'test-other')
        data_points = PartnerAnalyticsDataPoint.objects.filter(
            slug=ACCESS_ODATA
        )
        self.assertEqual(data_points.count(), 0)

    @mock.patch(
        'corehq.apps.analytics.utils.partner_analytics.get_number_of_mobile_workers',
        _get_fake_number_of_mobile_workers
    )
    @mock.patch(
        'corehq.apps.analytics.utils.partner_analytics.get_number_of_web_users',
        _get_fake_number_of_web_users
    )
    @mock.patch(
        'corehq.apps.analytics.utils.partner_analytics.get_number_of_submissions',
        _get_fake_number_of_submissions
    )
    @mock.patch('corehq.apps.analytics.utils.partner_analytics.send_HTML_email')
    def test_send_partner_emails(self, mock_send_HTML_email):
        generate_monthly_mobile_worker_statistics(self.year, self.month)
        generate_monthly_web_user_statistics(self.year, self.month)
        generate_monthly_submissions_statistics(self.year, self.month)
        track_partner_access(ACCESS_ODATA, 'test-001')
        track_partner_access(ACCESS_ODATA, 'test-001')
        track_partner_access(ACCESS_ODATA, 'test-002')
        track_partner_access(ACCESS_ODATA, 'test-003')
        track_partner_access(ACCESS_ODATA, 'test-003')
        track_partner_access(ACCESS_ODATA, 'test-003')
        send_partner_emails(self.year, self.month)
        headers, body = get_csv_details_for_partner(self.contact, self.year, self.month)
        self.assertListEqual(headers, ['Title', 'Project Space', 'Value'])
        self.assertListEqual(body, [
            ['Number of Mobile Workers', 'test-001', 10],
            ['Number of Mobile Workers', 'test-002', 20],
            ['Number of Mobile Workers', 'test-003', 30],
            ['Number of Submissions', 'test-001', 11],
            ['Number of Submissions', 'test-002', 22],
            ['Number of Submissions', 'test-003', 33],
            ['Number of Web Users', 'test-001', 11],
            ['Number of Web Users', 'test-002', 21],
            ['Number of Web Users', 'test-003', 31],
            ['OData Access', 'test-001', 2],
            ['OData Access', 'test-002', 1],
            ['OData Access', 'test-003', 3],
        ])
        self.assertEqual(mock_send_HTML_email.call_count, 1)
        email_args = mock_send_HTML_email.call_args_list
        self.assertEqual(
            email_args[0][0][0],
            "CommCare HQ Analytics Report: Helping Earth {month_name} {year}".format(
                month_name=calendar.month_name[self.month],
                year=self.year,
            )
        )
        self.assertEqual(
            email_args[0][0][1],
            self.contact.emails,
        )
        self.assertEqual(
            email_args[0][1]['file_attachments'][0]['title'],
            "Helping Earth_analytics_{year}_{month}".format(
                year=self.year,
                month=self.month,
            )
        )


class TestGetCsvValue(SimpleTestCase):

    def test_returns_string_if_value_is_string(self):
        value = _get_csv_value("foo")
        self.assertIsInstance(value, str)

    def test_returns_integer_if_value_is_integer(self):
        value = _get_csv_value(10)
        self.assertIsInstance(value, int)

    def test_returns_string_if_value_is_other(self):
        value = _get_csv_value(PartnerAnalyticsContact)
        self.assertIsInstance(value, str)
