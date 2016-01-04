from django.contrib.auth.models import User
from django.test import TestCase
from corehq.apps.tour.models import GuidedTour
from corehq.apps.tour.tours import StaticGuidedTour
from corehq.apps.users.models import WebUser

TEST_TOUR = StaticGuidedTour('test_tour', 'path/to/fake_tour.html')


class GuidedTourTest(TestCase):

    def setUp(self):
        self.web_user = WebUser.create('test-tour-domain', 'tourtester@mail.com', 'test123')
        self.test_user = User.objects.get_by_natural_key(self.web_user.username)

    def test_new_tour(self):
        self.assertTrue(TEST_TOUR.is_enabled(self.test_user))

    def test_mark_as_seen(self):
        GuidedTour.mark_as_seen(self.test_user, TEST_TOUR.slug)
        self.assertFalse(TEST_TOUR.is_enabled(self.test_user))

    def tearDown(self):
        self.web_user.delete()
