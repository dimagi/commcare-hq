import threading

from django.test import SimpleTestCase
from corehq.util.quickcache import quickcache
from time import sleep


@quickcache(['key'])
def generate_value(key, call_tracker, duration=0):
    call_tracker['calls'] = call_tracker['calls'] + 1
    sleep(duration)
    return f'hello {key}'


def set_value(call_tracker, duration):
    generate_value('world', call_tracker, duration)


def clear_cache(delay):
    sleep(delay)
    generate_value.clear('world', None)


class TestQuickcacheRace(SimpleTestCase):
    def setUp(self):
        generate_value.clear('world', None)
        self.call_tracker = {'calls': 0}
        self.threads = []

    def generateAfterSeconds(self, seconds):
        self.threads.append(threading.Thread(target=set_value, args=(self.call_tracker, seconds,)))

    def clearAfterSeconds(self, seconds):
        self.threads.append(threading.Thread(target=clear_cache, args=(seconds,)))

    def runThreads(self):
        [t.start() for t in self.threads]
        [t.join() for t in self.threads]

    def test_clear_works_as_intended(self):
        self.generateAfterSeconds(1)
        self.clearAfterSeconds(1.2)
        self.runThreads()

        generate_value('world', self.call_tracker)

        # generate_value was called twice, because it was cleared correctly
        self.assertEqual(self.call_tracker['calls'], 2)

    def test_clear_overridden(self):
        self.generateAfterSeconds(1)
        self.clearAfterSeconds(.5)
        self.runThreads()

        generate_value('world', self.call_tracker)

        # generate_value was only called once, because the first call returned
        # after the clear succeeded
        self.assertEqual(self.call_tracker['calls'], 1)
