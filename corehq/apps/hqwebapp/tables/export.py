import io

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext as _

from django_tables2.views import SingleTableMixin
from memoized import memoized

from couchexport.export import export_from_tables
from couchexport.models import Format


class TableExportException(Exception):
    pass


class TableExportConfig:
    """
    Configuration for export functionality.
    Attributes:
        export_format (str): Override to set the export format from backend. Defaults to XLS_2007.
        export_file_name (str): Name for the exported file (without extension). Defaults to the class name.
        export_sheet_name (str): Name for the worksheet. Defaults to export_file_name
    """
    export_format = None
    export_file_name = None
    export_sheet_name = None

    EXPORT_CONFIG_KEYS = {"export_file_name", "export_format", "export_sheet_name"}

    _SUPPORTED_FORMATS = [
        Format.CSV,
        Format.UNZIPPED_CSV,
        Format.XLS,
        Format.XLS_2007,
        Format.HTML,
        Format.ZIPPED_HTML,
        Format.JSON
    ]

    @memoized
    def get_export_sheet_name(self):
        return self.export_sheet_name or self.get_export_file_name()

    @memoized
    def get_export_file_name(self):
        return self.export_file_name or self.__class__.__name__

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
        exclude_columns_in_export (tuple): Columns to exclude from the export. Defaults to empty tuple.
    Usage:
        - Inherit this mixin in a view that uses django-tables2.
        - Define `table_class` as the django-tables2 table class to use.
        - Optionally set `export_format`, `export_file_name`, and `export_sheet_name` to customize export
          configurations.
        - Trigger export by calling the `trigger_export()` method.
    """

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
        return self.table_class(data=self.get_table_data())

    def trigger_export(self):
        self._validate_export_dependencies()
        return self._trigger_async_export()

    def _validate_export_dependencies(self):
        if not getattr(self, 'request', None):
            raise ImproperlyConfigured("TableExportMixin requires `self.request`.")
        if not getattr(self, 'table_class', None):
            raise ImproperlyConfigured("TableExportMixin requires `self.table_class`.")

    def _trigger_async_export(self):
        # TODO: Implement the logic to trigger an asynchronous export task.
        pass
