from collections import defaultdict
from corehq.apps.users.models import DomainMembershipError

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse, resolve, Resolver404
from django.utils.translation import get_language

from corehq.apps.domain.models import Domain
from corehq.tabs import extension_points
from corehq.tabs.exceptions import UrlPrefixFormatError, UrlPrefixFormatsSuggestion
from corehq.tabs.utils import sidebar_to_dropdown, dropdown_dict
from memoized import memoized
from django.core.cache.utils import make_template_fragment_key
from dimagi.utils.web import get_url_base


def url_is_location_safe(url):
    from corehq.apps.locations.permissions import is_location_safe
    url = url.split(get_url_base())[-1] if url else None
    try:
        match = resolve(url)
    except Resolver404:
        return False
    # pass empty request, since we should exclude any url that requires request context
    return is_location_safe(match.func, None, match.args, match.kwargs)


class UITab(object):
    title = None
    view = None
    fragment_prefix_name = 'header_tab'  # NOTE: This must match the string value used in the menu_main template

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
        self._project = project

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
    def divider(self):
        return dropdown_dict(None, is_divider=True)

    @property
    def project(self):
        if not self._project and self.domain:
            self._project = Domain.get_by_name(self.domain)
        return self._project

    @property
    def request_path(self):
        return self._request.get_full_path()

    @property
    def can_access_all_locations(self):
        """Is this a web user who can access project-wide data?"""
        return getattr(self._request, 'can_access_all_locations', True)

    @property
    def dropdown_items(self):
        return sidebar_to_dropdown(sidebar_items=self.sidebar_items,
                                   domain=self.domain, current_url=self.url)

    @property
    def filtered_dropdown_items(self):
        items = self.dropdown_items
        tab_name = self.__class__.__name__
        items.extend([
            dropdown_dict(**item)
            for item in extension_points.uitab_dropdown_items(
                tab_name, self, domain=self.domain, request=self._request
            )
        ])

        if self.can_access_all_locations:
            return items

        filtered = []
        for item in items:
            if url_is_location_safe(item['url']):
                filtered.append(item)
        return filtered

    @property
    def sidebar_items(self):
        return []

    @property
    @memoized
    def filtered_sidebar_items(self):
        items = self.sidebar_items
        tab_name = self.__class__.__name__
        items.extend(extension_points.uitab_sidebar_items(
            tab_name=tab_name, tab=self, domain=self.domain, request=self._request
        ))
        grouped = defaultdict(list)
        headings_order = []
        for heading, pages in items:
            if heading not in headings_order:
                headings_order.append(heading)
            grouped[heading].extend(pages)
        items = [
            (heading, grouped[heading]) for heading in headings_order
        ]

        if self.can_access_all_locations:
            return items

        filtered = []
        for heading, pages in items:
            safe_pages = [p for p in pages if url_is_location_safe(p['url'])]
            if safe_pages:
                filtered.append((heading, safe_pages))
        return filtered

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

        # Run tab-specific logic first, so that dropdown generation can assume any necessary data is present
        try:
            if not self._is_viewable:
                return False
        except AttributeError:
            return False

        if not self.can_access_all_locations:
            if self.dropdown_items and not self.filtered_dropdown_items:
                # location-safe filtering makes this whole tab inaccessible
                return False

            # Just a button tab, determine if it's location safe
            if not self.dropdown_items and not url_is_location_safe(self.url):
                return False

        return True

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
        # Use self._request.domain instead of self.domain to generate url-prefixes
        # because the latter might have a normalized domain name which might not match the
        # domain name mentioned in the URL. for example domain-name 'hq_test' is normalized to
        # 'hq-test'
        return [url_prefix_format.format(domain=getattr(self._request, 'domain', None))
                for url_prefix_format in self.url_prefix_formats]

    def get_url_prefix_formats_suggestion(self):
        import six.moves.urllib.parse
        accepted_urls = []
        # sorted shortest first
        all_urls = sorted(
            six.moves.urllib.parse.urlparse(url).path
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
    def create_compound_cache_param(cls, tab_name, domain, user_id, role_version, is_active,
            language, use_bootstrap5):
        params = [tab_name, str(domain), str(user_id), str(role_version), str(is_active),
                  str(language), str(use_bootstrap5)]
        return '|'.join(params)

    @classmethod
    def clear_dropdown_cache(cls, domain, user):
        try:
            user_role = user.get_role(domain, allow_enterprise=True)
            role_version = user_role.cache_version if user_role else None
        except DomainMembershipError:
            role_version = None

        language = get_language()

        cls.clear_dropdown_cache_impl(domain, user._id, role_version, language)

    @classmethod
    def clear_dropdown_cache_impl(cls, domain, user_id, role_version, language):
        keys = []
        for use_bootstrap5 in True, False:
            for is_active in True, False:
                fragment_param = cls.create_compound_cache_param(
                    cls.class_name(),
                    domain,
                    user_id,
                    role_version,
                    is_active,
                    language,
                    use_bootstrap5)
                keys.append(make_template_fragment_key(cls.fragment_prefix_name, [fragment_param]))

        cache.delete_many(keys)

    @classmethod
    def clear_dropdown_cache_for_all_domain_users(cls, domain):
        from corehq.apps.users.models import CouchUser
        for user_id in CouchUser.ids_by_domain(domain):
            user = CouchUser.get_by_user_id(user_id)
            cls.clear_dropdown_cache(domain, user)

    @property
    def css_id(self):
        return self.__class__.__name__

    @classmethod
    def class_name(cls):
        return cls.__name__
