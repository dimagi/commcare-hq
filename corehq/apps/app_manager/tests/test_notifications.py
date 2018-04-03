# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from mock import patch, Mock
from corehq.apps.app_manager.views.notifications import notify_event


class NotificationsTests(SimpleTestCase):

    def test_notify_event(self):
        couch_user = Mock()
        couch_user._id = '123'
        couch_user.username = 'emilie'
        with patch('corehq.apps.app_manager.views.notifications.RedisMessage'), \
                patch('corehq.apps.app_manager.views.notifications.RedisPublisher'), \
                patch('corehq.apps.app_manager.views.notifications.json_format_datetime') as format_patch, \
                patch('corehq.apps.app_manager.views.notifications.json') as json_patch:
            format_patch.return_value = 'maintenant'

            message = 'Émilie, vous avez de nouveaux messages.'
            notify_event('domain', couch_user, 'app_id', 'form_unique_id', message)

            notification = ('Émilie, vous avez de nouveaux messages.')
            json_patch.dumps.assert_called_with({
                'domain': 'domain',
                'user_id': '123',
                'username': 'emilie',
                'text': notification,
                'timestamp': 'maintenant',
            })
