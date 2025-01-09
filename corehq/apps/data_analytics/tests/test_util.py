from django.test import SimpleTestCase

from corehq.apps.data_analytics.tasks import summarize_user_counts


class TestSummarizeUserCounts(SimpleTestCase):
    def test_summarize_user_counts(self):
        self.assertEqual(
            summarize_user_counts({'a': 1, 'b': 10, 'c': 2}, n=0),
            {(): 13},
        )
        self.assertEqual(
            summarize_user_counts({'a': 1, 'b': 10, 'c': 2}, n=1),
            {'b': 10, (): 3},
        )
        self.assertEqual(
            summarize_user_counts({'a': 1, 'b': 10, 'c': 2}, n=2),
            {'b': 10, 'c': 2, (): 1},
        )
        self.assertEqual(
            summarize_user_counts({'a': 1, 'b': 10, 'c': 2}, n=3),
            {'a': 1, 'b': 10, 'c': 2, (): 0},
        )
        self.assertEqual(
            summarize_user_counts({'a': 1, 'b': 10, 'c': 2}, n=4),
            {'a': 1, 'b': 10, 'c': 2, (): 0},
        )
