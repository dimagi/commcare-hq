from django.shortcuts import render
import json
from corehq.apps.reports.standard import export
from corehq.apps.reports.models import FormExportSchema, HQGroupExportConfiguration
from corehq.apps.reports.standard.export import DeidExportReport
from couchexport.models import SavedExportSchema, ExportColumn, ExportTable, ExportSchema, Format
from django.utils.translation import ugettext as _
from couchexport.util import SerializableFunction


class CustomExportHelper(object):

    ExportSchemaClass = NotImplemented
    ExportReport = NotImplemented
    export_title = NotImplemented

    subclasses_map = NotImplemented  # implemented below

    @classmethod
    def make(cls, request, *args, **kwargs):
        export_type = request.GET.get('type', 'form')
        return cls.subclasses_map[export_type](request, *args, **kwargs)

    def update_custom_params(self):
        pass

    class DEID(object):
        options = (
            ('', ''),
            ('Sensitive ID', 'couchexport.deid.deid_ID'),
            ('Sensitive Date', 'couchexport.deid.deid_date'),
        )

    def __init__(self, request, domain, export_id=None):
        self.request = request
        self.domain = domain
        self.export_type = request.GET.get('type', 'form')
        self.presave = False

        if export_id:
            self.custom_export = self.ExportSchemaClass.get(export_id)
            # also update the schema to include potential new stuff
            self.custom_export.update_schema()

            # enable configuring saved exports from this page
            saved_group = HQGroupExportConfiguration.get_for_domain(self.domain)
            self.presave = export_id in saved_group.custom_export_ids

            assert(self.custom_export.doc_type == 'SavedExportSchema')
            assert(self.custom_export.type == self.export_type)
            assert(self.custom_export.index[0] == domain)
        else:
            self.custom_export = self.ExportSchemaClass(type=self.export_type)

    def parse_non_json_post(self):
        table = self.request.POST["table"]
        cols = self.request.POST['order'].strip().split()

        def export_cols():
            for col in cols:
                transform = self.request.POST.get('%s transform' % col) or None
                if transform:
                    transform = SerializableFunction.loads(transform)
                yield dict(
                    index=col,
                    display=self.request.POST["%s display" % col],
                    transform=transform
                )

        export_cols = list(export_cols())

        export_table = dict(
            index=table,
            display=self.custom_export.name,
            columns=export_cols
        )
        return {
            'tables': [export_table],
        }

    def update_custom_export(self):
        """
        Updates custom_export object from the request
        and saves to the db
        """
        schema = ExportSchema.get(self.request.POST["schema"])
        self.custom_export.index = schema.index
        self.custom_export.schema_id = self.request.POST["schema"]
        self.custom_export.name = self.request.POST["name"]
        self.custom_export.default_format = self.request.POST["format"] or Format.XLS_2007
        self.custom_export.is_safe = bool(self.request.POST.get('is_safe'))

        self.presave = bool(self.request.POST.get('presave'))

        try:
            post_data = json.loads(self.request.raw_post_data)
        except ValueError:
            post_data = self.parse_non_json_post()

        self.custom_export.tables = [
            ExportTable.wrap(table)
            for table in post_data['tables']
        ]

        table_dict = dict((t.index, t) for t in self.custom_export.tables)
        for table in self.custom_export.tables:
            if table.index in table_dict:
                table_dict[table.index].columns = table.columns
            else:
                self.custom_export.tables.append(
                    ExportTable(
                        index=table.index,
                        display=self.custom_export.name,
                        columns=table.columns
                    )
                )

        self.update_custom_params()

        self.custom_export.save()

        if self.presave:
            HQGroupExportConfiguration.add_custom_export(self.domain, self.custom_export.get_id)
        else:
            HQGroupExportConfiguration.remove_custom_export(self.domain, self.custom_export.get_id)

    def get_response(self):
        slug = self.ExportReport.slug

        def show_deid_column():
            for table_config in self.custom_export.table_configuration:
                for col in table_config['column_configuration']:
                    if col['transform']:
                        return True
            return False

        return render(self.request, "reports/reportdata/customize_export.html", {
            "saved_export": self.custom_export,
            "deid_options": self.DEID.options,
            "presave": self.presave,
            "DeidExportReport_name": DeidExportReport.name,
            "table_configuration": self.custom_export.table_configuration,
            "slug": slug,
            "domain": self.domain,
            "show_deid_column": show_deid_column(),
            'back_url': self.ExportReport.get_url(domain=self.domain),
            'export_title': self.export_title,
        })


class FormCustomExportHelper(CustomExportHelper):

    ExportSchemaClass = FormExportSchema
    ExportReport = export.ExcelExportReport

    @property
    def export_title(self):
        return _('Export Submissions to Excel')

    def __init__(self, request, domain, export_id=None):
        super(FormCustomExportHelper, self).__init__(request, domain, export_id)
        self.custom_export.app_id = request.GET.get('app_id')

    def update_custom_params(self):
        e = self.custom_export
        e.include_errors = bool(self.request.POST.get("include-errors"))
        e.app_id = self.request.POST.get('app_id')


class CaseCustomExportHelper(CustomExportHelper):

    ExportSchemaClass = SavedExportSchema
    ExportReport = export.CaseExportReport

    @property
    def export_title(self):
        return _('Export Cases, Referrals, and Users')


CustomExportHelper.subclasses_map = {
    'form': FormCustomExportHelper,
    'case': CaseCustomExportHelper,
}