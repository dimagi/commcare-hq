from unittest.mock import Mock
from django.test import SimpleTestCase

import pytest

from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.es.profiling import ESQueryProfiler
from corehq.apps.reports.standard import ESQueryProfilerMixin


class TestESQueryProfilerMixin(SimpleTestCase):

    def test_search_class_not_defined(self):

        class ProfiledReport(ESQueryProfilerMixin):
            profiler_enabled = True
            # `search_class` is not defined

        with pytest.raises(
            ValueError,
            match='^You must define a search_class attribute.'
        ):
            ProfiledReport()

    def test_search_class(self):

        class ProfiledReport(ESQueryProfilerMixin):
            profiler_enabled = True
            search_class = CaseSearchES

            def __init__(self, *args, **kwargs):
                self.request = Mock(GET={})
                super().__init__(*args, **kwargs)

        report = ProfiledReport()
        assert report.search_class.__name__ == 'ProfiledSearchClass'
        assert isinstance(report.profiler, ESQueryProfiler)
        assert report.profiler.search_class is CaseSearchES
        assert issubclass(report.search_class, report.profiler.search_class)

    def test_debug_mode_not_superuser(self):

        class ProfiledReport(ESQueryProfilerMixin):
            profiler_enabled = True
            search_class = CaseSearchES

            def __init__(self, *args, **kwargs):
                self.request = Mock(
                    GET={'debug': 'true'},
                    couch_user=Mock(is_superuser=False),
                )
                super().__init__(*args, **kwargs)

        report = ProfiledReport()
        assert report.debug_mode is False

    def test_debug_mode_true(self):

        class ProfiledReport(ESQueryProfilerMixin):
            profiler_enabled = True
            search_class = CaseSearchES

            def __init__(self, *args, **kwargs):
                self.request = Mock(
                    GET={'debug': 'true'},
                    couch_user=Mock(is_superuser=True),
                )
                super().__init__(*args, **kwargs)

        report = ProfiledReport()
        assert report.debug_mode is True

    def test_debug_mode_not_boolean(self):

        class ProfiledReport(ESQueryProfilerMixin):
            profiler_enabled = True
            search_class = CaseSearchES

            def __init__(self, *args, **kwargs):
                self.request = Mock(GET={'debug': 'yeah-not-so-much-bro'})
                super().__init__(*args, **kwargs)

        with pytest.raises(ValueError):
            ProfiledReport()

    def test_profiler_none(self):

        class ProfiledReport(ESQueryProfilerMixin):
            profiler_enabled = False
            search_class = CaseSearchES

            def __init__(self, *args, **kwargs):
                self.request = Mock(GET={})
                super().__init__(*args, **kwargs)

        report = ProfiledReport()
        assert report.profiler is None

    def test_profiler_enabled_true(self):

        class ProfiledReport(ESQueryProfilerMixin):
            profiler_enabled = True
            search_class = CaseSearchES

            def __init__(self, *args, **kwargs):
                self.request = Mock(GET={})
                super().__init__(*args, **kwargs)

        report = ProfiledReport()
        assert report.profiler is not None

    def test_profiler_enabled_false(self):

        class ProfiledReport(ESQueryProfilerMixin):
            profiler_enabled = False
            search_class = CaseSearchES

            def __init__(self, *args, **kwargs):
                self.request = Mock(GET={})
                super().__init__(*args, **kwargs)

        report = ProfiledReport()
        assert report.profiler is None
