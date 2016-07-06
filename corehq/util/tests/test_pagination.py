import itertools

from django.test.testcases import SimpleTestCase
from fakecouch import FakeCouchDb

from corehq.util.pagination import ResumableFunctionIterator


class TestResumableFunctionIterator(SimpleTestCase):

    def setUp(self):
        self.couch_db = FakeCouchDb()
        self.batches = [
            list(range(0, 3)),
            list(range(3, 6)),
            list(range(6, 8)),
        ]
        self.all_items = list(itertools.chain(*self.batches))
        self.itr = self.get_iterator()

    def tearDown(self):
        self.couch_db.reset()

    def get_iterator(self):
        def next_args(last_item, *args, **kwargs):
            if last_item is None:
                return [0], {}

            [batch_number] = args
            return [batch_number + 1], {}

        def data_provider(batch_number):
            try:
                return self.batches[batch_number]
            except IndexError:
                return []

        itr = ResumableFunctionIterator("test", data_provider, next_args)
        itr.couch_db = self.couch_db
        return itr

    def test_iteration(self):
        self.assertEqual(list(self.itr), self.all_items)

    def test_resume_iteration(self):
        itr = iter(self.itr)
        self.assertEqual([next(itr) for i in range(6)], self.all_items[:6])
        # stop/resume iteration
        self.itr = self.get_iterator()
        self.assertEqual([item for item in self.itr], self.all_items[3:])

    def test_resume_iteration_after_complete_iteration(self):
        self.assertEqual(list(self.itr), self.all_items)
        # resume iteration
        self.itr = self.get_iterator()
        self.assertEqual(list(self.itr), [])

    def test_discard_state(self):
        self.assertEqual(list(self.itr), self.all_items)
        self.itr.discard_state()

        self.itr = self.get_iterator()
        self.assertEqual(list(self.itr), self.all_items)

    def test_iteration_with_progress_info(self):
        itr = iter(self.itr)
        self.assertEqual([next(itr) for i in range(6)], self.all_items[:6])
        self.assertEqual(self.itr.progress_info, {})
        self.itr.progress_info = {"visited": 6}
        # stop/resume iteration
        self.itr = self.get_iterator()
        self.assertEqual(self.itr.progress_info, {"visited": 6})
        self.itr.progress_info = {"visited": "six"}
        # stop/resume iteration
        self.itr = self.get_iterator()
        self.assertEqual(self.itr.progress_info, {"visited": "six"})
        self.assertEqual([item for item in self.itr], self.all_items[3:])
