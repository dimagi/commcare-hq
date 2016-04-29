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

    # Tuple of prefixes that this UITab claims e.g.
    #   ('/a/{domain}/reports/', '/a/{domain}/otherthing/')
    # This is a required field.
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
    def _is_viewable(self):
        """
        Whether the tab should be displayed.  Subclass implementations can skip
        checking whether domain, couch_user, or project is not None before
        accessing an attribute of them -- this property is accessed in
        should_show and wrapped in a try block that returns False in the
        case of an AttributeError for any of those variables.

        """
        raise NotImplementedError()

    @memoized
    def should_show(self):
        if not self.show_by_default and not self.is_active_tab:
            return False

        try:
            return self._is_viewable
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
    def clear_dropdown_cache(cls, domain, user_id):
        for is_active in True, False:
            key = make_template_fragment_key('header_tab', [
                cls.class_name(),
                domain,
                is_active,
                user_id,
                get_language(),
            ])
            cache.delete(key)

    @property
    def css_id(self):
        return self.__class__.__name__

    @classmethod
    def class_name(cls):
        return cls.__name__
