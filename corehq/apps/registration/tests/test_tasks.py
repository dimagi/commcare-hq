import datetime
from django.test import TestCase

from corehq.apps.registration.models import AsyncSignupRequest
from corehq.apps.registration.tasks import delete_old_async_signup_requests


class TestDeleteAsyncSignupRequestsTask(TestCase):

    def tearDown(self):
        super().tearDown()
        AsyncSignupRequest.objects.all().delete()

    def test_request_greater_than_one_day_is_deleted(self):
        """
        Ensure that AsyncSignupRequests older than one day are all deleted.
        """
        yesterday = datetime.datetime.utcnow() - datetime.timedelta(days=1, minutes=2)

        first_request = AsyncSignupRequest.objects.create(username="firstuser@gmail.com")
        first_request.date_created = yesterday  # done here because of auto_now_add
        first_request.save()

        second_request = AsyncSignupRequest.objects.create(username="seconduser@gmail.com")
        second_request.date_created = yesterday
        second_request.save()

        self.assertEqual(AsyncSignupRequest.objects.count(), 2)
        delete_old_async_signup_requests()
        self.assertEqual(AsyncSignupRequest.objects.count(), 0)

    def test_request_less_than_one_day_are_kept(self):
        """
        Ensure that AsyncSignupRequests less than 1 day old are not deleted.
        """
        AsyncSignupRequest.objects.create(username="today1@gmail.com")
        AsyncSignupRequest.objects.create(username="today2@gmail.com")
        self.assertEqual(AsyncSignupRequest.objects.count(), 2)
        delete_old_async_signup_requests()
        self.assertEqual(AsyncSignupRequest.objects.count(), 2)
