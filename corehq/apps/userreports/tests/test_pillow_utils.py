from django.core.cache.backends.locmem import LocMemCache
from freezegun import freeze_time
from unmagic import fixture

from ..pillow_utils import TaskCoordinator


class TestTaskCoordinator:

    def setup_method(self, __):
        self.django_cache = self._django_cache()

    def test_should_run(self):
        coord = TaskCoordinator('test', 5, self.django_cache)
        assert coord.should_run(1)
        assert not coord.should_run(1)

    def test_timeout(self):
        coord = TaskCoordinator('test', 5, self.django_cache)
        with freeze_time('2020-01-01T00:00:00Z'):
            assert coord.should_run(1)

        with freeze_time('2020-01-01T00:00:10Z'):
            assert coord.should_run(1)

    def test_reset(self):
        coord = TaskCoordinator('test', 5, self.django_cache)
        other = TaskCoordinator('test', 5, self.django_cache)
        with freeze_time('2020-01-01T00:00:00Z'):
            assert coord.should_run(1)

        with freeze_time('2020-01-01T00:00:04Z'):
            assert not coord.should_run(1)
            coord.reset(1)
            assert coord.should_run(1)  # new timeout: 4 + 5 = 9
            assert not other.should_run(1)

        with freeze_time('2020-01-01T00:00:08Z'):
            assert not coord.should_run(1)
            assert not other.should_run(1)

        with freeze_time('2020-01-01T00:00:10Z'):
            assert coord.should_run(1)
            assert not other.should_run(1)

    def test_timeout_changed(self):
        coord = TaskCoordinator('test', 300, self.django_cache)  # long timeout
        with freeze_time('2020-01-01T00:00:00Z'):
            assert coord.should_run(1)

        coord = TaskCoordinator('test', 30, self.django_cache)  # short timeout
        with freeze_time('2020-01-01T00:01:00Z'):
            assert coord.should_run(1)

    def test_update_local_cache_from_redis(self):
        coord = TaskCoordinator('test', 30, self.django_cache)
        other = TaskCoordinator('test', 30, self.django_cache)
        with freeze_time('2020-01-01T00:00:00Z'):
            assert coord.should_run(1)

            assert not other.should_run(1)
            del other.django_cache  # should not be referenced on second call
            assert not other.should_run(1)

    def test_does_not_hit_django_cache_unnecessarily(self):
        coord = TaskCoordinator('test', 5, self.django_cache)
        with freeze_time('2020-01-01T00:00:00Z'):
            assert coord.should_run(1)

        del coord.django_cache  # should not be referenced
        with freeze_time('2020-01-01T00:00:03Z'):
            assert not coord.should_run(1)

    def test_concurrency(self):
        cache1 = TaskCoordinator('test', 60, self.django_cache)
        cache2 = TaskCoordinator('test', 60, self.django_cache)

        assert cache1.should_run(1)
        assert not cache2.should_run(1)

    def test_local_cache_pruning(self):
        coord = TaskCoordinator('test', 5, self.django_cache)
        with freeze_time('2020-01-01T00:00:00Z'):
            coord.should_run(1)
            coord.should_run(2)
            coord.should_run(3)
            assert len(coord.local_cache) == 3

        with freeze_time('2020-01-01T00:00:10Z'):
            coord.should_run(1)
            assert len(coord.local_cache) == 1

    @fixture
    def _django_cache():
        django_cache = LocMemCache(__name__, {})
        yield django_cache
        django_cache.clear()
