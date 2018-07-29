from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from corehq.apps.notifications.models import Notification, LastSeenNotification, IllegalModelStateException
from corehq.apps.users.models import WebUser


class NotificationTest(TestCase):

    def setUp(self):
        self.note = Notification.objects.create(content="info1", url="http://dimagi.com", type='info')

        self.user = User()
        self.user.username = 'mockmock@mockmock.com'
        self.user.save()
        self.couch_user = WebUser(username=self.user.username, domains=['test-dom'])

    def tearDown(self):
        self.note.delete()
        self.user.delete()

    def test_activate(self):
        notes = Notification.get_by_user(self.user, self.couch_user)
        self.assertEqual(len(notes), 0)
        self.note.activate()
        notes = Notification.get_by_user(self.user, self.couch_user)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['isRead'], False)

    def test_deactivate(self):
        self.note.activate()
        notes = Notification.get_by_user(self.user, self.couch_user)
        self.assertEqual(len(notes), 1)
        self.note.deactivate()
        notes = Notification.get_by_user(self.user, self.couch_user)
        self.assertEqual(len(notes), 0)

    def test_mark_as_read(self):
        self.note.activate()
        notes = Notification.get_by_user(self.user, self.couch_user)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['isRead'], False)
        self.note.mark_as_read(self.user)
        notes = Notification.get_by_user(self.user, self.couch_user)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['isRead'], True)

    def test_mark_active_as_last_seen(self):
        self.note.activate()
        self.note.set_as_last_seen(self.user)
        self.assertEqual(
            LastSeenNotification.get_last_seen_notification_date_for_user(self.user), self.note.activated
        )

    def test_mark_inactive_as_last_seen(self):
        with self.assertRaises(IllegalModelStateException):
            self.note.set_as_last_seen(self.user)

    def test_notification_created_before_user(self):
        self.note.activate()
        date_joined = self.user.date_joined
        notification_activated = date_joined - timedelta(days=1)
        Notification.objects.create(
            content="old notification", url="http://dimagi.com", type="info",
            activated=notification_activated, is_active=True
        )
        notes = Notification.get_by_user(self.user, self.couch_user)
        self.assertEqual(len(notes), 1)

    def test_domain_specific_notification(self):
        self.note.activate()
        notes = Notification.get_by_user(self.user, self.couch_user)
        self.assertEqual(len(notes), 1)

        # notification is for a domain the user is not a member of
        note1 = Notification.objects.create(
            content="dom notification", url="http://dimagi.com", type="info",
            domain_specific=True, domains=['dom']
        )
        note1.activate()
        notes = Notification.get_by_user(self.user, self.couch_user)
        self.assertEqual(len(notes), 1)

        #notification is for the users domain
        note2 = Notification.objects.create(
            content="test dom notification", url="http://dimagi.com", type="info",
            domain_specific=True, domains=['test-dom']
        )
        note2.activate()
        notes = Notification.get_by_user(self.user, self.couch_user)
        self.assertEqual(len(notes), 2)
