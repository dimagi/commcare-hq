from django.test import TestCase
import datetime
from dimagi.utils.dates import add_months
from corehq.apps.reports.standard.project_health import MonthlyPerformanceSummary
from corehq.apps.data_analytics.models import MALTRow
from corehq.const import MISSING_APP_ID
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users


class MonthlyPerformanceSummaryTests(TestCase):
    DOMAIN_NAME = "test"
    USERNAME = "testuser"
    USERNAME1 = "testuser1"
    USERNAME2 = "testuser2"
    USER_TYPE = "CommCareUser"
    now = datetime.datetime.utcnow()
    year, month = add_months(now.year, now.month, 1)
    month_as_date = datetime.date(year, month, 1)
    prev_month_as_date = datetime.date(year, month - 1, 1)

    @classmethod
    def setUpClass(cls):
        super(MonthlyPerformanceSummaryTests, cls).setUpClass()
        cls._setup_domain()
        cls._setup_users()
        cls._setup_malt_tables()
        users_in_group = []
        cls.prev_month = MonthlyPerformanceSummary(
            domain=cls.DOMAIN_NAME,
            performance_threshold=15,
            month=cls.prev_month_as_date,
            previous_summary=None,
            users=users_in_group,
            has_group_filter=False,
        )
        cls.month = MonthlyPerformanceSummary(
            domain=cls.DOMAIN_NAME,
            performance_threshold=15,
            month=cls.month_as_date,
            previous_summary=cls.prev_month,
            users=users_in_group,
            has_group_filter=False,
        )

    @classmethod
    def tearDownClass(cls):
        super(MonthlyPerformanceSummaryTests, cls).tearDownClass()
        delete_all_users()
        MALTRow.objects.all().delete()

    @classmethod
    def _setup_users(cls):
        cls.user = CommCareUser.create(cls.DOMAIN_NAME, cls.USERNAME, '*****')
        cls.user.save()
        cls.user1 = CommCareUser.create(cls.DOMAIN_NAME, cls.USERNAME1, '*****')
        cls.user1.save()

    @classmethod
    def _setup_domain(cls):
        cls.domain = Domain(name=cls.DOMAIN_NAME)
        cls.domain.save()

    @classmethod
    def _setup_malt_tables(cls):
        malt_user = MALTRow.objects.create(
            month=cls.month_as_date,
            user_id=cls.user._id,
            username=cls.USERNAME,
            domain_name=cls.DOMAIN_NAME,
            user_type=cls.USER_TYPE,
            num_of_forms=16,
            app_id=MISSING_APP_ID,
        )
        malt_user.save()
        malt_user1 = MALTRow.objects.create(
            month=cls.month_as_date,
            user_id=cls.user1._id,
            username=cls.USERNAME1,
            domain_name=cls.DOMAIN_NAME,
            user_type=cls.USER_TYPE,
            num_of_forms=16,
            app_id=MISSING_APP_ID,
        )
        malt_user1.save()
        malt_user_prev = MALTRow.objects.create(
            month=cls.prev_month_as_date,
            user_id=cls.user._id,
            username=cls.USERNAME,
            domain_name=cls.DOMAIN_NAME,
            user_type=cls.USER_TYPE,
            num_of_forms=15,
            app_id=MISSING_APP_ID,
        )
        malt_user_prev.save()

    def test_delta_active_additional_user(self):
        """
        delta_active() should return 1 when there is one additional user from previous month
        """
        self.assertEqual(self.month.delta_active, 1)

    def test_delta_active_no_user(self):
        """
        delta_active() should return this month's active users when there is no summary from previous month
        """
        self.assertEqual(self.prev_month.delta_active, 1)

    def test_number_of_active_users(self):
        """
        number_of_active_users() should return 1 user last month
        """
        self.assertEqual(self.prev_month.number_of_active_users, 1)

    def test_number_of_performing_users(self):
        """
        number_of_performing_users() should return two users who submitted 15 or more forms
        """
        self.assertEqual(self.month.number_of_performing_users, 2)

    def test_delta_performing_additional_user(self):
        """
        delta_performing() should return 1 when there is one more performing user
        """
        self.assertEqual(self.month.delta_performing, 1)

    def test_delta_performing_no_user(self):
        """
        delta_performing() should return this month's performing user1 when there is no summary from previous month
        """
        self.assertEqual(self.prev_month.delta_performing, 1)

    def test_get_all_user_stubs(self):
        """
        get_all_user_stubs() should contain two users from this month
        """
        self.assertEqual(len(self.month.get_all_user_stubs().keys()), 2)
