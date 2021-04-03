from datetime import datetime
from django.test import TestCase

from ..models import UserAccessLog, UserAgent


class TestUserAccessLogManager(TestCase):
    @staticmethod
    def get_kwargs(**kwargs):
        defaults = {
            'user_id': 'test_user',
            'action': 'login',
            'ip': '127.0.0.1',
            'path': '/login',
            'user_agent': 'Mozilla',
            'timestamp': datetime.utcnow()
        }

        defaults.update(kwargs)

        return defaults

    def test_create_generates_record(self):
        current_time = datetime.utcnow()
        kwargs = self.get_kwargs(timestamp=current_time)
        record = UserAccessLog.objects.create(**kwargs)

        self.assertEqual(record.user_id, 'test_user')
        self.assertEqual(record.action, 'login')
        self.assertEqual(record.ip, '127.0.0.1')
        self.assertEqual(record.path, '/login')
        self.assertEqual(record.user_agent, 'Mozilla')
        self.assertEqual(record.timestamp, current_time)

    def test_create_generates_record_in_database(self):
        kwargs = self.get_kwargs(user_id='test_user')
        created_record = UserAccessLog.objects.create(**kwargs)
        retrieved_record = UserAccessLog.objects.get(id=created_record.id)

        self.assertEqual(retrieved_record.user_id, 'test_user')

    def test_creates_user_agent_in_separate_table(self):
        kwargs = self.get_kwargs(user_agent='Chrome')
        UserAccessLog.objects.create(**kwargs)

        agent_record = UserAgent.objects.get(value='Chrome')
        self.assertEqual(agent_record.value, 'Chrome')

    def test_user_agent_is_truncated(self):
        long_agent_string = ('a' * 255) + ('b' * 255)
        kwargs = self.get_kwargs(user_agent=long_agent_string)
        record = UserAccessLog.objects.create(**kwargs)
        expected_agent = ('a' * 255)  # All the b's should have been truncated

        self.assertEqual(len(record.user_agent), 255)
        self.assertEqual(record.user_agent, expected_agent)
