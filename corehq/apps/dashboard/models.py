from __future__ import absolute_import
from django.urls import reverse, resolve, Resolver404
from corehq.tabs.uitab import url_is_location_safe
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.export.models.new import FormExportInstance, CaseExportInstance
from corehq.apps.export.views import ExportsPermissionsMixin, user_can_view_deid_exports
from corehq.apps.reports.models import ReportConfig, CaseExportSchema, FormExportSchema
from dimagi.utils.decorators.memoized import memoized


class TileConfigurationError(Exception):
    pass


class TileType(object):
    ICON = 'icon'
    PAGINATE = 'paginate'


class Tile(object):
    """This class creates the tile and its context
    when it's called by Django Angular's Remote Method Invocation.
    """

    def __init__(self, tile_config, request, in_data):
        if not isinstance(tile_config, TileConfiguration):
            raise TileConfigurationError(
                "tile_config must be an instance of TileConfiguration"
            )
        self.tile_config = tile_config
        self.request = request

        # this is the data provided by Django Angular's Remote Method Invocation
        self.in_data = in_data

    @property
    def is_visible(self):
        """Whether or not the tile is visible on the dashboard (permissions).
        :return: Boolean
        """
        if not self.request.can_access_all_locations:
            url = self.tile_config.get_url(self.request)
            try:
                match = resolve(url)
            except Resolver404:
                pass
            else:
                if 'domain' in match.kwargs and not url_is_location_safe(url):
                    return False
        return bool(self.tile_config.visibility_check(self.request))

    @property
    @memoized
    def context_processor(self):
        return self.tile_config.context_processor_class(
            self.tile_config, self.request, self.in_data
        )

    @property
    def context(self):
        """This is sent back to the Angular JS controller created the remote
        Remote Method Invocation of the Dashboard view.
        :return: dict
        """
        tile_context = {
            'slug': self.tile_config.slug,
            'helpText': self.tile_config.help_text,
            'analytics': {
                'usage_label': self.tile_config.analytics_usage_label,
                'workflow_labels': self.tile_config.analytics_workflow_labels,
            }
        }
        tile_context.update(self.context_processor.context)
        return tile_context


class TileConfiguration(object):

    def __init__(self, title, slug, icon, context_processor_class,
                 url=None, urlname=None, is_external_link=False,
                 visibility_check=None, url_generator=None,
                 help_text=None, analytics_usage_label=None,
                 analytics_workflow_labels=None):
        """
        :param title: The title of the tile
        :param slug: The tile's slug
        :param icon: The class of the icon
        :param context_processor: A Subclass of BaseTileContextProcessor
        :param url: the url that the icon will link to
        :param urlname: the urlname of the view that the icon will link to
        :param is_external_link: True if the tile opens links in new window/tab
        :param visibility_check: (optional) a lambda that accepts a request
        and urlname and returns a boolean value if the tile is visible to the
        user.
        :param url_generator: a lambda that accepts a request and returns
        a string that is the url the tile will take the user to if it's clicked
        :param help_text: (optional) text that will appear on hover of tile
        :param analytics_usage_label: (optional) label to be used in usage
        analytics event tracking.
        :param analytics_workflow_labels: (optional) label to be used in workflow
        analytics event tracking.
        """
        if not issubclass(context_processor_class, BaseTileContextProcessor):
            raise TileConfigurationError(
                "context processor must be subclass of BaseTileContextProcessor"
            )
        self.context_processor_class = context_processor_class
        self.title = title
        self.slug = slug
        self.icon = icon
        self.url = url
        self.urlname = urlname
        self.is_external_link = is_external_link
        self.visibility_check = (visibility_check
                                 or self._default_visibility_check)
        self.url_generator = url_generator or self._default_url_generator
        self.help_text = help_text
        self.analytics_usage_label = analytics_usage_label
        self.analytics_workflow_labels = analytics_workflow_labels if analytics_workflow_labels is not None else []

    @property
    def ng_directive(self):
        return self.context_processor_class.tile_type

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


class BaseTileContextProcessor(object):
    tile_type = None

    def __init__(self, tile_config, request, in_data):
        """
        :param tile_config: An instance of TileConfiguration
        :param request: An instance of HttpRequest
        :param in_data: A dictionary provided by Django Angular's
        Remote Method Invocation
        """
        self.request = request
        self.tile_config = tile_config
        self.in_data = in_data

    @property
    def context(self):
        """This is the context specific to the type of tile we're creating.
        :return: dict
        """
        raise NotImplementedError('context must be overridden')


class IconContext(BaseTileContextProcessor):
    """This type of tile is just an icon with a link to another page on HQ
    or an external link (like the help site).
    """
    tile_type = TileType.ICON

    @property
    def context(self):
        return {
            'url': self.tile_config.get_url(self.request),
            'icon': self.tile_config.icon,
            'isExternal': self.tile_config.is_external_link,
        }


class BasePaginatedTileContextProcessor(BaseTileContextProcessor):
    """A resource for serving data to the Angularjs PaginatedTileController
    for the hq.dashboard Angular JS module.
    To use, subclass this and override :total: and :paginated_items: properties.
    """
    tile_type = TileType.PAGINATE

    @property
    def context(self):
        return {
            'pagination': self.pagination_context,
            'default': {
                'show': self.tile_config.icon is not None,
                'icon': self.tile_config.icon,
                'url': self.tile_config.get_url(self.request),
            },
        }

    @property
    def pagination_data(self):
        """The data we READ to figure out the current pagination state.
        :return: dict
        """
        return self.in_data['pagination']

    @property
    def limit(self):
        """The maximum number of items for this page.
        :return: integer
        """
        return self.pagination_data.get('limit', 5)

    @property
    def current_page(self):
        """The current page that the paginator is on.
        :return: integer
        """
        return self.pagination_data.get('currentPage', 1)

    @property
    def skip(self):
        """The number of items to skip over to get to the current page in
        the list of paginated items (or in the queryset).
        :return: integer
        """
        return (self.current_page - 1) * self.limit

    @property
    def pagination_context(self):
        return {
            'total': self.total,
            'limit': self.limit,
            'currentPage': self.current_page,
            'paginatedItems': list(self.paginated_items),
        }

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

    @property
    def paginated_items(self):
        """The items (as dictionaries/objects) to be passed to the angularjs
        template for rendering. It's recommended that you use the
        _fmt_item() helper function to return the correctly formatted dict
        for each item.
        :return: list of dicts formatted with _fmt_item
        """
        raise NotImplementedError('pagination must be overridden')


class ReportsPaginatedContext(BasePaginatedTileContextProcessor):
    """Generates the Paginated context for the Reports Tile.
    """
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

    @property
    def paginated_items(self):
        reports = ReportConfig.by_domain_and_owner(
            self.request.domain, self.request.couch_user._id,
            limit=self.limit, skip=self.skip
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


class AppsPaginatedContext(BasePaginatedTileContextProcessor):
    """Generates the Paginated context for the Applications Tile.
    """

    @property
    def total(self):
        # todo: optimize this at some point. unfortunately applications_brief
        # doesn't have a reduce view and for now we'll avoid refactoring.
        return len(self.applications)

    @property
    @memoized
    def applications(self):
        return get_brief_apps_in_domain(self.request.domain)

    @property
    def paginated_items(self):
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

        apps = self.applications[self.skip:self.skip + self.limit]

        return [self._fmt_item(a.name,
                               _get_app_url(a)) for a in apps]


class DataPaginatedContext(BasePaginatedTileContextProcessor, ExportsPermissionsMixin):
    """Generates the Paginated context for the Data Tile."""
    domain = None

    def __init__(self, tile_config, request, in_data):
        self.domain = request.domain
        super(DataPaginatedContext, self).__init__(tile_config, request, in_data)

    @property
    def total(self):
        return len(self.case_exports) + len(self.form_exports)

    @property
    @memoized
    def has_deid_view_permissions(self):
        return user_can_view_deid_exports(self.domain, self.request.couch_user)

    @property
    @memoized
    def form_exports(self):
        exports = []
        if self.has_edit_permissions:
            from corehq.apps.export.dbaccessors import get_form_exports_by_domain
            exports = get_form_exports_by_domain(self.domain, self.has_deid_view_permissions)
        return exports

    @property
    @memoized
    def case_exports(self):
        exports = []
        if self.has_edit_permissions:
            from corehq.apps.export.dbaccessors import get_case_exports_by_domain
            exports = get_case_exports_by_domain(self.domain, self.has_deid_view_permissions)
        return exports

    @property
    def paginated_items(self):
        exports = (self.case_exports + self.form_exports)[self.skip:self.skip + self.limit]
        for export in exports:
            urlname = ''
            if isinstance(export, CaseExportInstance):
                urlname = 'new_export_download_cases'
            elif isinstance(export, FormExportInstance):
                urlname = 'new_export_download_forms'
            elif isinstance(export, CaseExportSchema):
                urlname = 'export_download_cases'
            elif isinstance(export, FormExportSchema):
                urlname = 'export_download_forms'
            if urlname:
                yield self._fmt_item(
                    export.name,
                    reverse(urlname, args=(self.request.domain, export.get_id))
                )
