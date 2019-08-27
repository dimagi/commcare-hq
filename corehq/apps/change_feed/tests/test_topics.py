
from django.test import SimpleTestCase

from corehq.apps.change_feed import data_sources, topics
from corehq.apps.change_feed.topics import get_topic_for_doc_type
from corehq.util.test_utils import generate_cases


class TopicTests(SimpleTestCase):
    pass


@generate_cases([
    ('CommCareCase', data_sources.SOURCE_COUCH, topics.CASE),
    ('CommCareCase', None, topics.CASE),
    ('CommCareCase', data_sources.SOURCE_SQL, topics.CASE_SQL),
    ('XFormInstance', data_sources.SOURCE_COUCH, topics.FORM),
    ('XFormInstance', None, topics.FORM),
    ('XFormInstance', data_sources.SOURCE_SQL, topics.FORM_SQL),
], TopicTests)
def test_get_topic_for_doc_type(self, doc_type, data_source, expected_topic):
    topic = get_topic_for_doc_type(doc_type, data_source)
    self.assertEqual(topic, expected_topic)
