import datetime

from django.test import RequestFactory, TestCase

from unittest import mock

from dimagi.utils.dates import add_months

from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.domain.models import Domain
from corehq.apps.es.fake.groups_fake import GroupESFake
from corehq.apps.es.fake.users_fake import UserESFake
from corehq.apps.groups.models import Group
from corehq.apps.reports.standard.project_health import (
    MonthlyPerformanceSummary,
    ProjectHealthDashboard,
)
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.const import MISSING_APP_ID


@mock.patch('corehq.apps.reports.standard.project_health.UserES', UserESFake)
class SetupProjectPerformanceMixin(object):
    DOMAIN_NAME = "test_domain"
    USERNAME = "testuser"
    USERNAME1 = "testuser1"
    USERNAME2 = "testuser2"
    WEB_USER = "webuser"
    USER_TYPE = "CommCareUser"
    now = datetime.datetime.utcnow()
    year, month = add_months(now.year, now.month, 1)
    month_as_date = datetime.date(year, month, 1)
    prev_month_as_date = datetime.date(now.year, now.month, 1)

    @classmethod
    def class_setup(cls):
        cls._setup_domain()
        cls._setup_users()
        cls._setup_malt_tables()

    @classmethod
    def class_teardown(cls):
        UserESFake.reset_docs()
        cls.domain.delete()

    @classmethod
    def make_mobile_worker(cls, username, domain=None):
        domain = domain or cls.domain
        user = CommCareUser.create(domain, username, '123', None, None)
        doc = user._doc
        doc['username.exact'] = doc['username']
        UserESFake.save_doc(doc)
        return user

    @classmethod
    def _setup_users(cls):
        cls.user = cls.make_mobile_worker(cls.USERNAME, cls.DOMAIN_NAME)
        cls.user1 = cls.make_mobile_worker(cls.USERNAME1, cls.DOMAIN_NAME)
        cls.user2 = cls.make_mobile_worker(cls.USERNAME2, cls.DOMAIN_NAME)

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


class MonthlyPerformanceSummaryTests(SetupProjectPerformanceMixin, TestCase):

    @classmethod
    def setUpClass(cls):
        super(MonthlyPerformanceSummaryTests, cls).setUpClass()
        cls.class_setup()
        users_in_group = []
        active_not_deleted_users = [cls.user._id, cls.user1._id, cls.user2._id]
        cls.prev_month = MonthlyPerformanceSummary(
            domain=cls.DOMAIN_NAME,
            performance_threshold=15,
            month=cls.prev_month_as_date,
            previous_summary=None,
            selected_users=users_in_group,
            active_not_deleted_users=active_not_deleted_users,
        )
        cls.month = MonthlyPerformanceSummary(
            domain=cls.DOMAIN_NAME,
            performance_threshold=15,
            month=cls.month_as_date,
            previous_summary=cls.prev_month,
            selected_users=users_in_group,
            active_not_deleted_users=active_not_deleted_users,
        )

    @classmethod
    def tearDownClass(cls):
        super(MonthlyPerformanceSummaryTests, cls).tearDownClass()
        cls.class_teardown()
        MALTRow.objects.all().delete()

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

    def test_helper_get_all_user_stubs(self):
        """
        _get_all_user_stubs() should contain two users from this month
        """
        self.assertEqual(len(list(self.month._get_all_user_stubs())), 2)


@mock.patch('corehq.apps.reports.standard.project_health.GroupES', GroupESFake)
class ProjectHealthDashboardTest(SetupProjectPerformanceMixin, TestCase):
    request = RequestFactory().get('/project_health')

    GROUP_NAME = 'group'

    @classmethod
    def setUpClass(cls):
        super(ProjectHealthDashboardTest, cls).setUpClass()
        cls.class_setup()
        cls._setup_group()
        cls._assign_user_to_group()
        cls._setup_web_user()
        cls._setup_dashboard()

    @classmethod
    def tearDownClass(cls):
        cls.class_teardown()
        GroupESFake.reset_docs()
        super(ProjectHealthDashboardTest, cls).tearDownClass()

    @classmethod
    def _setup_group(cls):
        group = Group(name=cls.GROUP_NAME, domain=cls.DOMAIN_NAME)
        GroupESFake.save_doc(group._doc)
        cls.group = group

    @classmethod
    def _assign_user_to_group(cls):
        cls.group.add_user(cls.user)

    @classmethod
    def _setup_web_user(cls):
        cls.web_user = WebUser.create(cls.DOMAIN_NAME, cls.WEB_USER, '*****', None, None)
        cls.web_user.save()
        cls.request.couch_user = cls.web_user

    @classmethod
    def _setup_dashboard(cls):
        cls.dashboard = ProjectHealthDashboard(cls.request)
        cls.dashboard.domain = cls.DOMAIN_NAME

    def test_get_users_by_group_filter(self):
        """
        get_users_by_group_filter() should return 1 user based on group_id provided
        """
        group_id = self.group.get_id
        users_by_group = self.dashboard.get_users_by_group_filter([group_id])
        self.assertEqual(len(users_by_group), 1)
