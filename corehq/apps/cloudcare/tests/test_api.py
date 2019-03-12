from __future__ import absolute_import
from __future__ import unicode_literals
import json

from django.urls import reverse
from django.test import TestCase
from mock import patch

from corehq.apps.cloudcare.views import ReadableQuestions
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username


TEST_DOMAIN = "test-cloudcare-domain"


class ReadableQuestionsAPITest(TestCase):
    """
    Tests some of the Case API functions
    """
    domain = TEST_DOMAIN

    @classmethod
    def setUpClass(cls):
        super(ReadableQuestionsAPITest, cls).setUpClass()
        cls.project = create_domain(cls.domain)
        cls.password = "****"
        cls.username = format_username('reed', cls.domain)

        cls.user = CommCareUser.create(
            cls.domain,
            cls.username,
            cls.password
        )

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.project.delete()
        super(ReadableQuestionsAPITest, cls).tearDownClass()

    def test_readable_questions(self):
        instanceXml = '''
        <data>
          <question1>ddd</question1>
        </data>
        '''
        self.client.login(username=self.username, password=self.password)
        with patch('corehq.apps.cloudcare.views.readable.get_questions', lambda x, y, z: []):
            result = self.client.post(
                reverse(ReadableQuestions.urlname, args=[self.domain]),
                {
                    'app_id': '123',
                    'xmlns': 'abc',
                    'instanceXml': instanceXml,
                }
            )
        self.assertEqual(result.status_code, 200)
        self.assertIn('form_data', json.loads(result.content))
