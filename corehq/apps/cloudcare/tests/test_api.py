from __future__ import absolute_import
from __future__ import unicode_literals
import json
import uuid

from django.urls import reverse
from django.test import TestCase
from mock import patch

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from corehq.apps.cloudcare.views import ReadableQuestions
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


TEST_DOMAIN = "test-cloudcare-domain"


def _child_case_type(type):
    return "%s-child" % type


def _type_to_name(type):
    return "%s-name" % type


def _create_case(user, type, close=False, **extras):
    case_id = uuid.uuid4().hex
    domain = extras.pop('domain', TEST_DOMAIN)
    blocks = [CaseBlock(
        create=True,
        case_id=case_id,
        case_name=_type_to_name(type),
        case_type=type,
        user_id=user.user_id,
        owner_id=user.user_id,
        **extras
    ).as_xml()]
    if close:
        blocks.append(CaseBlock(
            create=False,
            case_id=case_id,
            close=True,
        ).as_xml())
    post_case_blocks(blocks, {'domain': domain})
    case = CaseAccessors(domain).get_case(case_id)
    assert case.closed == close
    return case


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
