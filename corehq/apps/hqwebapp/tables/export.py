import io

from django.core.exceptions import ImproperlyConfigured
from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.utils.translation import gettext as _

from django_tables2.rows import BoundRows
from django_tables2.views import SingleTableMixin
from memoized import memoized

from corehq.apps.hqwebapp.tables.elasticsearch.tables import ElasticTable
from couchexport.export import export_from_tables
from couchexport.models import Format
from dimagi.utils.web import json_request

from corehq.apps.hqwebapp.tasks import export_all_rows_task


class TableExportException(Exception):
    pass


class TableExportConfig:
    """
    Configuration for export functionality.
    Attributes:
        export_format (str): Override to set the export format from backend. Defaults to XLS_2007.
        export_sheet_name (str): Name for the worksheet. Defaults to the class name.
    """
    export_format = None
    export_sheet_name = None

    EXPORT_CONFIG_KEYS = {"export_format", "export_sheet_name"}

    _SUPPORTED_FORMATS = [
        Format.CSV,
        Format.UNZIPPED_CSV,
        Format.XLS,
        Format.XLS_2007,
        Format.HTML,
        Format.ZIPPED_HTML,
        Format.JSON
    ]

    def get_export_sheet_name(self):
        return self.export_sheet_name or self.__class__.__name__

    @memoized
    def get_export_format(self):
        export_format = self.export_format or self.request.GET.get('format', Format.XLS_2007)
        self._validate_export_format(export_format)
        return export_format

    def _validate_export_format(self, export_format):
        if export_format not in self._SUPPORTED_FORMATS:
            raise TableExportException(
                _("Unsupported export format: {}. Supported formats are: {}".format(
                    export_format, ','.join(self._SUPPORTED_FORMATS)
                ))
            )

    def config_as_dict(self):
        return {key: getattr(self, key) for key in self.EXPORT_CONFIG_KEYS}


class TableExportMixin(TableExportConfig, SingleTableMixin):
    """
    Mixin to add export functionality to django-tables2 based views.
    Attributes:
        report_title (str): Title of the report, used in the export file name. Defaults to the class name.
        exclude_columns_in_export (tuple): Columns to exclude from the export. Defaults to empty tuple.
    Usage:
        - Inherit this mixin in a view that uses django-tables2.
        - Define `table_class` as the django-tables2 table class to use.
        - Optionally set `export_format`, `export_file_name`, and `export_sheet_name` to customize export
          configurations.
        - Trigger export by calling the `trigger_export()` method.
    """

    report_title = None
    exclude_columns_in_export = ()

    def export_to_file(self):
        file = io.BytesIO()
        export_from_tables(self._export_table_data, file, self.get_export_format())
        return file

    @property
    def _export_table_data(self):
        """
        Returns data in the format expected by export_from_tables:
        [[sheet_name, [headers, row1, row2, ...]]]
        """
        table = self.get_table_for_export().as_values(exclude_columns=self.exclude_columns_in_export)
        return [[self.get_export_sheet_name(), table]]

    def get_table_for_export(self):
        """
        Can be overridden for customization.
        """
        table = self.table_class(data=self.get_table_data())
        # Elastic Table uses queryset for data which gets evaluated lazily on pagination.
        # As export is not paginated, we need to ensure that all records are fetched.
        if isinstance(table, ElasticTable):
            table.request = self.request
            table.rows = BoundRows(data=table.data.get_all_records(), table=table)
        table.context = self.export_table_context(table)
        return table

    def export_table_context(self, table):
        """
        Can be overridden to provide additional context for the export.
        """
        return {}

    def trigger_export(self, recipient_list=None, subject=None):
        self._validate_export_dependencies()
        return self._trigger_async_export(recipient_list, subject)

    def _validate_export_dependencies(self):
        if not getattr(self, 'request', None):
            raise ImproperlyConfigured("TableExportMixin requires `self.request`.")
        if not getattr(self, 'table_class', None):
            raise ImproperlyConfigured("TableExportMixin requires `self.table_class`.")

    def _trigger_async_export(self, recipient_list, subject):
        export_all_rows_task.delay(
            class_path=f"{self.__class__.__module__}.{self.__class__.__name__}",
            export_context=self._get_export_context(),
            recipient_list=recipient_list,
            subject=subject,
        )
        return HttpResponse(_("Export is being generated. You will receive an email when it is ready."))

    def _get_export_context(self):
        """Returns context needed to reconstruct the view for async export"""
        return {
            "domain": self.request.domain,
            "can_access_all_locations": self.request.can_access_all_locations,
            "user_id": self.request.couch_user.user_id,
            "request_params": json_request(self.request.GET),
            "config": self.config_as_dict(),
            "report_title": self.get_report_title(),
        }

    @memoized
    def get_report_title(self):
        return self.report_title or self.__class__.__name__

    @classmethod
    def reconstruct_from_export_context(cls, context):
        """Reconstructs view instance from the export context to be used in the celery task"""
        from corehq.apps.users.models import CouchUser

        request = HttpRequest()
        request.method = 'GET'
        request.GET.update(context['request_params'])
        request.domain = context['domain']
        request.couch_user = CouchUser.get_by_user_id(context['user_id'])
        request.can_access_all_locations = context['can_access_all_locations']

        view = cls()
        view.request = request
        for config_key, config_value in context['config'].items():
            setattr(view, config_key, config_value)

        return view
