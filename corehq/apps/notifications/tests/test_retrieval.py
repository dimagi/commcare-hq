from django.contrib.auth.models import User
from django.test import TestCase

from corehq.apps.notifications.models import Notification

class NotificationTest(TestCase):

    def setUp(self):
        Notification.objects.create(content="info1", url="http://dimagi.com", type='info')

        self.user = User()
        self.user.username = 'mockmock@mockmock.com'
        self.user.save()

    def tearDown(self):
        Notification.objects.all().delete()
        self.user.delete()

    def test_activate(self):
        notes = Notification.get_by_user(self.user)
        self.assertEqual(len(notes), 0)
        Notification.objects.first().activate()
        notes = Notification.get_by_user(self.user)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['isRead'], False)

    def test_deactivate(self):
        note = Notification.objects.first()
        note.activate()
        notes = Notification.get_by_user(self.user)
        self.assertEqual(len(notes), 1)
        note.deactivate()
        notes = Notification.get_by_user(self.user)
        self.assertEqual(len(notes), 0)

    def test_mark_as_read(self):
        Notification.objects.first().activate()
        notes = Notification.get_by_user(self.user)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['isRead'], False)
        Notification.mark_as_read(notes[0]['id'], self.user)
        notes = Notification.get_by_user(self.user)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['isRead'], True)
        
