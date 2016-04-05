from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.utils.translation import get_language
from corehq.tabs.utils import sidebar_to_dropdown, path_starts_with_url
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.django.cache import make_template_fragment_key


class UITab(object):
    title = None
    view = None

    dispatcher = None

    # must be instance of GaTracker
    ga_tracker = None

    def __init__(self, request, current_url_name, domain=None, couch_user=None,
                 project=None):

        self.domain = domain
        self.couch_user = couch_user
        self.project = project

        # This should not be considered as part of the subclass API unless it
        # is necessary. Try to add new explicit parameters instead.
        self._request = request
        self._current_url_name = current_url_name

    @property
    def request_path(self):
        return self._request.get_full_path()

    @property
    def dropdown_items(self):
        # todo: add default implementation which looks at sidebar_items and
        # sees which ones have is_dropdown_visible or something like that.
        return sidebar_to_dropdown(sidebar_items=self.sidebar_items,
                                   domain=self.domain, current_url_name=self.url)

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
    @memoized
    def urls(self):
        urls = [self.url] if self.url else []
        try:
            for name, section in self.sidebar_items:
                urls.extend(item['url'] for item in section)
        except Exception:
            # tried to get urls for another tab on a page that doesn't provide
            # the necessary couch_user, domain, project, etc. value
            pass

        return urls

    @property
    @memoized
    def subpage_url_names(self):
        """
        List of all url names of subpages of sidebar items that get
        displayed only when you're on that subpage.
        """
        names = []

        try:
            for name, section in self.sidebar_items:
                names.extend(subpage['urlname']
                             for item in section
                             for subpage in item.get('subpages', []))
        except Exception:
            pass

        return names

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
