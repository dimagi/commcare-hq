class CouchCachedReportMixin(object):
    """
        Use this mixin for caching reports as objects in couch.
    """
    _cached_report = None
    @property
    def cached_report(self):
        if not self._cached_report:
            self._cached_report = self._fetch_cached_report()
        return self._cached_report

    def _fetch_cached_report(self):
        """
            Here's where you generate your cached report.
        """
        raise NotImplementedError
