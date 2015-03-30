from django.utils.cache import _generate_cache_header_key
from corehq.util.quickcache import quickcache, QuickCache

DEFAULT_EXPIRY = 60 * 60  # an hour
CACHE_PREFIX = 'hq.reports'  # a namespace where cache keys go


class _ReportQuickCache(QuickCache):
    """
    Just like QuickCache, but intercepts the function call to abort caching
    under certain conditions
    """
    def __call__(self, *args, **kwargs):
        report = args[0]
        if report.is_cacheable and _is_valid(report):
            return super(_ReportQuickCache, self).__call__(*args, **kwargs)
        else:
            return self.fn(*args, **kwargs)


def _is_valid(report):
    """
    checks if this meets the preconditions for being allowed in the cache
    """
    try:
        return (
            report.request.domain
            and report.request.couch_user._id
            and report.request.get_full_path().startswith(
                '/a/{domain}/'.format(domain=report.request.domain)
            )
        )
    except AttributeError:
        return False


def _custom_vary_on(report):
    """
    signature is intentionally restricted to a single argument
    to prevent @request_cache() from decorating a method that has non-self args
    """
    return [
        _generate_cache_header_key(CACHE_PREFIX, report.request),
        report.request.domain,
        report.request.couch_user._id,
    ]


def request_cache(expiry=DEFAULT_EXPIRY):
    """
    A decorator that can be used on a method of a GenericReportView subclass

    or any other class that provides the following properties:
      - self.request (a django request object, with .domain and .couch_user)
      - self.is_cacheable (boolean)

    """

    return quickcache(vary_on=_custom_vary_on,
                      timeout=expiry, helper_class=_ReportQuickCache)
