from datetime import datetime, timezone, date
import uuid
from dateutil.relativedelta import relativedelta

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from corehq.apps.app_manager.models import Application
from corehq.apps.users.credentials_issuing import (
    get_app_names_by_id,
    get_username_cred_id_dict,
    has_consecutive_months,
)
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import (
    ActivityLevel,
    UserCredential,
    ConnectIDUserLink,
)


class TestHasConsecutiveMonths(SimpleTestCase):

    def setUp(self):
        super().setUp()
        self.three_months = [
            datetime.now(timezone.utc) - relativedelta(months=1),
            datetime.now(timezone.utc) - relativedelta(months=3),
            datetime.now(timezone.utc) - relativedelta(months=7),
            datetime.now(timezone.utc) - relativedelta(months=4),
            datetime.now(timezone.utc) - relativedelta(months=5),
        ]

        self.two_months_across_years = [
            date(year=2023, month=12, day=1),
            date(year=2024, month=3, day=1),
            date(year=2024, month=1, day=1),
        ]

    def test_has_consecutive_months(self):
        assert has_consecutive_months(self.three_months, required_months=3) is True
        assert has_consecutive_months(self.three_months, required_months=2) is True

    def test_consecutive_month_across_years(self):
        assert has_consecutive_months(self.two_months_across_years, required_months=2) is True

    def test_no_consecutive_months(self):
        assert has_consecutive_months(self.three_months, required_months=4) is False


class TestGetUsernameCredIDDict(TestCase):
    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user1 = User.objects.create(username='user1', password='password')
        cls.user2 = User.objects.create(username='user2', password='password')
        ConnectIDUserLink.objects.create(
            connectid_username=cls.user1.username,
            commcare_user=cls.user1,
            domain=cls.domain,
        )
        ConnectIDUserLink.objects.create(
            connectid_username=cls.user2.username,
            commcare_user=cls.user2,
            domain=cls.domain,
        )

        cls.cred1 = UserCredential.objects.create(
            domain=cls.domain,
            user_id=cls.user1.id,
            username=cls.user1.username,
            app_id=1,
            activity_level=ActivityLevel.ONE_MONTH
        )
        cls.cred2 = UserCredential.objects.create(
            domain=cls.domain,
            user_id=cls.user2.id,
            username=cls.user2.username,
            app_id=1,
            activity_level=ActivityLevel.ONE_MONTH
        )
        cls.cred3 = UserCredential.objects.create(
            domain=cls.domain,
            user_id=cls.user1.id,
            username=cls.user1.username,
            app_id=3,
            activity_level=ActivityLevel.THREE_MONTHS
        )

    @classmethod
    def tearDownClass(cls):
        UserCredential.objects.all().delete()
        delete_all_users()
        super().tearDownClass()

    def test_get_username_cred_id_dict(self):
        res = get_username_cred_id_dict([self.cred1, self.cred2, self.cred3])
        assert res == {
            (self.cred1.app_id, ActivityLevel.ONE_MONTH): [
                (self.user1.username, self.cred1.id),
                (self.user2.username, self.cred2.id)
            ],
            (self.cred3.app_id, ActivityLevel.THREE_MONTHS): [
                (self.user1.username, self.cred3.id)
            ]
        }

    def test_no_user_credentials(self):
        res = get_username_cred_id_dict([])
        assert res == {}


class TestGetAppNamesByID(TestCase):
    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.one_month_app = Application.new_app(
            domain=cls.domain,
            name="One Month Test App",
        )
        cls.one_month_app._id = uuid.uuid4().hex
        cls.one_month_app.save()
        cls.three_month_app = Application.new_app(
            domain=cls.domain,
            name="Three Month Test App",
        )
        cls.three_month_app._id = uuid.uuid4().hex
        cls.three_month_app.save()

        cls.cred1 = UserCredential(
            domain=cls.domain,
            user_id=1,
            username='user1',
            app_id=cls.one_month_app.id,
            activity_level=ActivityLevel.ONE_MONTH
        )
        cls.cred2 = UserCredential(
            domain=cls.domain,
            user_id=1,
            username='user1',
            app_id=cls.three_month_app.id,
            activity_level=ActivityLevel.THREE_MONTHS
        )

    @classmethod
    def tearDownClass(cls):
        UserCredential.objects.all().delete()
        super().tearDownClass()

    def test_get_app_names_by_id(self):
        res = get_app_names_by_id([self.cred1, self.cred2])
        assert res == {
            self.one_month_app.id: self.one_month_app.name,
            self.three_month_app.id: self.three_month_app.name,
        }

    def test_missing_app(self):
        missing_app_id = 21
        missing_app_cred = UserCredential(
            domain=self.domain,
            user_id=3,
            username='user3',
            app_id=missing_app_id,
            activity_level=ActivityLevel.ONE_MONTH,
        )
        res = get_app_names_by_id([self.cred1, missing_app_cred])
        assert res == {
            self.one_month_app.id: self.one_month_app.name,
            missing_app_id: missing_app_id,
        }

    def test_no_user_credentials(self):
        res = get_app_names_by_id([])
        assert res == {}
