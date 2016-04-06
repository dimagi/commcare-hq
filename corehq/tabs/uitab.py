from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.utils.translation import get_language
from corehq.tabs.exceptions import UrlPrefixFormatError, UrlPrefixFormatsSuggestion
from corehq.tabs.utils import sidebar_to_dropdown
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.django.cache import make_template_fragment_key
from django.conf import settings


class UITab(object):
    title = None
    view = None

    dispatcher = None

    # if a tab subclass has an expensive sidebar_items
    # it should define its url_prefix_formats here explicitly
    # e.g. ('/a/{domain}/reports/', '/a/{domain}/otherthing/')
    # renderer can quickly tell which tab to highlight as active
    url_prefix_formats = ()
    show_by_default = True

    # must be instance of GaTracker
    ga_tracker = None

    def __init__(self, request, domain=None, couch_user=None, project=None):

        self.domain = domain
        self.couch_user = couch_user
        self.project = project

        # This should not be considered as part of the subclass API unless it
        # is necessary. Try to add new explicit parameters instead.
        self._request = request

        # must be set manually (i.e. `tab.is_active_tab = True`)
        self.is_active_tab = False

        # Do some preemptive checks on the subclass's configuration (if DEBUG)
        if settings.DEBUG:
            if not self.url_prefix_formats:
                raise UrlPrefixFormatsSuggestion(
                    'Class {} must define url_prefix_formats. Try\n'
                    'url_prefix_formats = {}'
                    .format(self.__class__.__name__,
                            self.get_url_prefix_formats_suggestion()))
            for url_prefix_formats in self.url_prefix_formats:
                try:
                    url_prefix_formats.format(domain='')
                except (IndexError, KeyError):
                    raise UrlPrefixFormatError(
                        'Class {} has url_prefix_format has an issue: {}'
                        .format(self.__class__.__name__, url_prefix_formats))

    @property
    def request_path(self):
        return self._request.get_full_path()

    @property
    def dropdown_items(self):
        return sidebar_to_dropdown(sidebar_items=self.sidebar_items,
                                   domain=self.domain, current_url=self.url)

    @property
    @memoized
    def sidebar_items(self):
        if self.dispatcher:
            return self.dispatcher.navigation_sections(request=self._request, domain=self.domain)
        else:
            return []

    @property
    def is_viewable(self):
        """
        Whether the tab should be displayed.  Subclass implementations can skip
        checking whether domain, couch_user, or project is not None before
        accessing an attribute of them -- this property is accessed in
        real_is_viewable and wrapped in a try block that returns False in the
        case of an AttributeError for any of those variables.

        """
        raise NotImplementedError()

    @property
    @memoized
    def real_is_viewable(self):
        if not self.show_by_default and not self.is_active_tab:
            return False

        try:
            return self.is_viewable
        except AttributeError:
            return False

    @property
    @memoized
    def url(self):
        try:
            if self.domain:
                return reverse(self.view, args=[self.domain])
        except Exception:
            pass

        try:
            return reverse(self.view)
        except Exception:
            return None

    @property
    def url_prefixes(self):
        return [url_prefix_format.format(domain=self.domain)
                for url_prefix_format in self.url_prefix_formats]

    def get_url_prefix_formats_suggestion(self):
        import urlparse
        accepted_urls = []
        # sorted shortest first
        all_urls = sorted(
            urlparse.urlparse(url).path
            # replace the actual domain with {domain}
            .replace('/a/{}'.format(self.domain), '/a/{domain}')
            for url in self._get_inferred_urls
        )
        # accept only urls that don't start with an already-accepted prefix
        for url in all_urls:
            for prefix in accepted_urls:
                if url.startswith(prefix):
                    break
            else:
                accepted_urls.append(url)
        return tuple(accepted_urls)

    @property
    @memoized
    def _get_inferred_urls(self):
        urls = [self.url] if self.url else []
        for name, section in self.sidebar_items:
            urls.extend(item['url'] for item in section)

        return urls

    @classmethod
    def clear_dropdown_cache(cls, request, domain):
        for is_active in True, False:
            if hasattr(cls, 'get_view'):
                view = cls.get_view(domain)
            else:
                view = cls.view
            key = make_template_fragment_key('header_tab', [
                domain,
                None,  # tab.org should be None for any non org page
                view,
                is_active,
                request.couch_user.get_id,
                get_language(),
            ])
            cache.delete(key)

    @property
    def css_id(self):
        return self.__class__.__name__
