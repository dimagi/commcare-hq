from unittest.mock import Mock

from django.test import SimpleTestCase

import pytest

from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.es.profiling import ESQueryProfiler
from corehq.apps.reports.standard import ESQueryProfilerMixin
from corehq.util.test_utils import flag_enabled


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
        # ESQueryProfilerMixin replaces `report.search_class` with one
        # that wraps the original and profiles query execution times.
        assert report.search_class.__name__ == 'ProfiledSearchClass'
        assert isinstance(report.profiler, ESQueryProfiler)
        assert report.profiler.search_class is ProfiledReport.search_class
        assert issubclass(report.search_class, report.profiler.search_class)

    @flag_enabled('REPORT_TIMING_PROFILING')
    def test_debug_mode_not_superuser(self):

        class ProfiledReport(ESQueryProfilerMixin):
            profiler_enabled = True
            search_class = CaseSearchES

            def __init__(self, *args, **kwargs):
                self.request = Mock(couch_user=Mock(is_superuser=False))
                super().__init__(*args, **kwargs)

        report = ProfiledReport()
        assert report.debug_mode is False

    @flag_enabled('REPORT_TIMING_PROFILING')
    def test_debug_mode_true(self):

        class ProfiledReport(ESQueryProfilerMixin):
            profiler_enabled = True
            search_class = CaseSearchES

            def __init__(self, *args, **kwargs):
                self.request = Mock(couch_user=Mock(is_superuser=True))
                super().__init__(*args, **kwargs)

        report = ProfiledReport()
        assert report.debug_mode is True

    def test_debug_mode_toggle_disabled(self):

        class ProfiledReport(ESQueryProfilerMixin):
            profiler_enabled = True
            search_class = CaseSearchES

            def __init__(self, *args, **kwargs):
                self.request = Mock(couch_user=Mock(is_superuser=True))
                super().__init__(*args, **kwargs)

        report = ProfiledReport()
        assert report.debug_mode is False

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
