from django.test import SimpleTestCase

from corehq.apps.change_feed import document_types, topics
from corehq.apps.change_feed.topics import get_topic_for_doc_type
from corehq.util.test_utils import generate_cases


class TopicTests(SimpleTestCase):
    pass


@generate_cases([
    ('CommCareCase', topics.CASE_SQL),
    ('XFormInstance', topics.FORM_SQL),
    (document_types.LEDGER_DOC_TYPE, topics.LEDGER),
    (document_types.SMS_DOC_TYPE, topics.SMS),
    (document_types.SYNCLOG_SQL_DOC_TYPE, topics.SYNCLOG_SQL),
], TopicTests)
def test_get_topic_for_doc_type(self, doc_type, expected_topic):
    topic = get_topic_for_doc_type(doc_type)
    self.assertEqual(topic, expected_topic)


def test_tests_use_test_topics():
    assert all(topic.startswith('test-') for topic in topics.ALL), topics.ALL
