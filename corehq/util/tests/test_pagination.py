import itertools

from django.test.testcases import SimpleTestCase
from fakecouch import FakeCouchDb

from corehq.util.pagination import ResumableFunctionIterator, ArgsProvider


class TestArgsProvider(ArgsProvider):
    def get_initial_args(self):
        return [0], {}

    def get_next_args(self, last_item, *last_args, **last_kwargs):
        if last_item is None:
            raise StopIteration

        [batch_number] = last_args
        return [batch_number + 1], {}


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

    def get_iterator(self, missing_items=None):
        def data_provider(batch_number):
            try:
                return self.batches[batch_number]
            except IndexError:
                return []

        itr = ResumableFunctionIterator('test', data_provider, TestArgsProvider())
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

    def test_resume_iteration_after_exhaustion(self):
        itr = iter(self.itr)
        self.assertEqual(list(itr), self.all_items)
        # resume iteration
        self.batches.append([8, 9])
        self.itr = self.get_iterator()
        self.assertEqual(list(self.itr), [8, 9])

    def test_resume_iteration_after_legacy_completion(self):
        itr = iter(self.itr)
        self.assertEqual(list(itr), self.all_items)
        state = self.itr.state
        state.complete = True
        state.args = state.kwargs = None
        self.itr._save_state()
        # attempt to resume yields no new items
        self.batches.append([8, 9])
        self.itr = self.get_iterator()
        self.assertEqual(list(self.itr), [])

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

    def test_iteration_with_iterator_detail(self):
        itr = iter(self.itr)
        self.assertEqual([next(itr) for i in range(6)], self.all_items[:6])
        self.assertEqual(self.itr.get_iterator_detail('progress'), None)
        self.itr.set_iterator_detail('progress', {"visited": 6})
        # stop/resume iteration
        self.itr = self.get_iterator()
        self.assertEqual(self.itr.get_iterator_detail('progress'), {"visited": 6})
        self.itr.set_iterator_detail('progress', {"visited": "six"})
        # stop/resume iteration
        self.itr = self.get_iterator()
        self.assertEqual(self.itr.get_iterator_detail('progress'), {"visited": "six"})
        self.assertEqual([item for item in self.itr], self.all_items[3:])
