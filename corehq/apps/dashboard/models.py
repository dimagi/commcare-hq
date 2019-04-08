from __future__ import absolute_import
from __future__ import unicode_literals
from django.urls import reverse, resolve, Resolver404
from corehq.tabs.uitab import url_is_location_safe
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.export.models.new import FormExportInstance, CaseExportInstance
from corehq.apps.export.views.utils import ExportsPermissionsManager
from corehq.apps.saved_reports.models import ReportConfig
from memoized import memoized


class Tile(object):

    def __init__(self, request, title, slug, icon, paginator_class=None,
                 url=None, urlname=None, visibility_check=None,
                 url_generator=None, help_text=None):
        """
        :param request: Request object for the page
        :param title: The title of the tile
        :param slug: The tile's slug
        :param icon: The class of the icon
        :param paginator_class: A Subclass of TilePaginator
        :param url: the url that the icon will link to
        :param urlname: the urlname of the view that the icon will link to
        :param visibility_check: (optional) a lambda that accepts a request
        and urlname and returns a boolean value if the tile is visible to the
        user.
        :param url_generator: a lambda that accepts a request and returns
        a string that is the url the tile will take the user to if it's clicked
        :param help_text: (optional) text that will appear on hover of tile
        """
        self.request = request
        self.paginator_class = paginator_class
        self.title = title
        self.slug = slug
        self.icon = icon
        self.url = url
        self.urlname = urlname
        self.visibility_check = (visibility_check or self._default_visibility_check)
        self.url_generator = url_generator or self._default_url_generator
        self.help_text = help_text

    @property
    def is_visible(self):
        """Whether or not the tile is visible on the dashboard (permissions).
        :return: Boolean
        """
        if not self.request.can_access_all_locations:
            url = self.get_url(self.request)
            try:
                match = resolve(url)
            except Resolver404:
                pass
            else:
                if 'domain' in match.kwargs and not url_is_location_safe(url):
                    return False
        return bool(self.visibility_check(self.request))

    @property
    @memoized
    def paginator(self):
        return self.paginator_class(self.request)

    def get_url(self, request):
        if self.urlname is not None:
            return self.url_generator(self.urlname, request)
        return self.url

    @staticmethod
    def _default_url_generator(urlname, request):
        return reverse(urlname, args=[request.domain])

    @staticmethod
    def _default_visibility_check(request):
        return True


class TilePaginator(object):
    """A container for logic to page through a particular type of item (e.g., applications).
    To use, subclass this and override :total: and :_paginated_items:.
    """

    def __init__(self, request):
        self.request = request

    @staticmethod
    def _fmt_item(name,
                  url,
                  description=None,
                  full_name=None):
        """This is the format that the paginator expects items to be in
        so that the template can be fully rendered.
        :param name: string
        :param url: string
        :param description: string. optional.
        If present, a popover will appear to the left of the list item.
        :param full_name: string. optional.
        If present, set the popover title.
        If these two values are present, display an icon that link to a secondary url when the line is hovered.
        :return:
        """

        return {
            'name_full': full_name or name,
            'name': name,
            'description': description,
            'url': url,
        }

    @property
    def total(self):
        """The total number of objects being paginated over.
        :return: integer
        """
        raise NotImplementedError('total must return an int')

    def paginated_items(self, current_page, items_per_page):
        """The items (as dictionaries/objects). It's recommended that you use the
        _fmt_item() helper function to return correctly formatted dicts.
        :return: list of dicts formatted with _fmt_item
        """
        return self._paginated_items(items_per_page, (current_page - 1) * items_per_page)

    def _paginated_items(self, items_per_page, skip):
        """Helper for paginated_items, with index of start item already calculated"""
        raise NotImplementedError('_paginated_items must be overridden')


class ReportsPaginator(TilePaginator):

    @property
    def total(self):
        key = ["name", self.request.domain, self.request.couch_user._id]
        results = ReportConfig.get_db().view(
            'reportconfig/configs_by_domain',
            include_docs=False,
            startkey=key,
            endkey=key+[{}],
            reduce=True,
        ).all()
        return results[0]['value'] if results else 0

    def _paginated_items(self, items_per_page, skip):
        reports = ReportConfig.by_domain_and_owner(
            self.request.domain, self.request.couch_user._id,
            limit=items_per_page, skip=skip
        )
        for report in reports:
            yield self._fmt_item(
                report.name,
                report.url,
                description="%(desc)s (%(date)s)" % {
                    'desc': report.description,
                    'date': report.date_description,
                },
                full_name=report.full_name
            )


class AppsPaginator(TilePaginator):

    @property
    def total(self):
        return len(self.applications)

    @property
    @memoized
    def applications(self):
        apps = get_brief_apps_in_domain(self.request.domain)
        apps = sorted(apps, key=lambda item: item.name.lower())
        return apps

    def _paginated_items(self, items_per_page, skip):
        def _get_app_url(app):
            return (
                _get_view_app_url(app)
                if self.request.couch_user.can_edit_apps()
                else _get_release_manager_url(app)
            )

        def _get_view_app_url(app):
            return reverse('view_app', args=[self.request.domain, app.get_id])

        def _get_release_manager_url(app):
            return reverse('release_manager', args=[self.request.domain, app.get_id])

        apps = self.applications[skip:skip + items_per_page]

        return [self._fmt_item(a.name,
                               _get_app_url(a)) for a in apps]


class DataPaginator(TilePaginator):
    def __init__(self, *args, **kwargs):
        super(DataPaginator, self).__init__(*args, **kwargs)
        self.permissions = ExportsPermissionsManager(None, self.request.domain, self.request.couch_user)

    @property
    def total(self):
        return len(self.case_exports) + len(self.form_exports)

    @property
    @memoized
    def form_exports(self):
        exports = []
        if self.permissions.has_form_export_permissions:
            from corehq.apps.export.dbaccessors import get_form_exports_by_domain
            exports = get_form_exports_by_domain(self.request.domain, self.permissions.has_deid_view_permissions)
        return exports

    @property
    @memoized
    def case_exports(self):
        exports = []
        if self.permissions.has_case_export_permissions:
            from corehq.apps.export.dbaccessors import get_case_exports_by_domain
            exports = get_case_exports_by_domain(self.request.domain, self.permissions.has_deid_view_permissions)
        return exports

    def _paginated_items(self, items_per_page, skip):
        exports = (self.form_exports + self.case_exports)
        exports = sorted(exports, key=lambda item: item.name.lower())
        exports = exports[skip:skip + items_per_page]
        for export in exports:
            urlname = ''
            if isinstance(export, CaseExportInstance):
                urlname = 'new_export_download_cases'
            elif isinstance(export, FormExportInstance):
                urlname = 'new_export_download_forms'
            if urlname:
                yield self._fmt_item(
                    export.name,
                    reverse(urlname, args=(self.request.domain, export.get_id))
                )
