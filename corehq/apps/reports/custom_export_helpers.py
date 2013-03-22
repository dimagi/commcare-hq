from django.shortcuts import render
import json
from corehq.apps.reports.standard import export
from corehq.apps.reports.models import FormExportSchema, HQGroupExportConfiguration
from corehq.apps.reports.standard.export import DeidExportReport
from couchexport.models import SavedExportSchema, ExportTable, ExportSchema
from django.utils.translation import ugettext as _
from dimagi.utils.decorators.memoized import memoized


class CustomExportHelper(object):

    ExportSchemaClass = NotImplemented
    ExportReport = NotImplemented
    export_title = NotImplemented
    allow_deid = False

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
            (_('Sensitive ID'), 'couchexport.deid.deid_ID'),
            (_('Sensitive Date'), 'couchexport.deid.deid_date'),
        )
        json_options = [{'label': label, 'value': value}
                        for label, value in options]

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

    @property
    @memoized
    def post_data(self):
        return json.loads(self.request.raw_post_data)

    def update_custom_export(self):
        """
        Updates custom_export object from the request
        and saves to the db
        """

        post_data = self.post_data

        custom_export_json = post_data['custom_export']

        SAFE_KEYS = ('default_format', 'is_safe', 'name', 'schema_id')

        for key in SAFE_KEYS:
            self.custom_export[key] = custom_export_json[key]

        # update the custom export index (to stay in sync)
        schema_id = self.custom_export.schema_id
        schema = ExportSchema.get(schema_id)
        self.custom_export.index = schema.index

        self.presave = post_data['presave']

        self.custom_export.tables = [
            ExportTable.wrap(table)
            for table in custom_export_json['tables']
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

        def show_deid_column():
            for table_config in self.custom_export.table_configuration:
                for col in table_config['column_configuration']:
                    if col['transform']:
                        return True
            return False

        return render(self.request, "reports/reportdata/customize_export.html", {
            "custom_export": self.custom_export,
            "deid_options": self.DEID.json_options,
            "presave": self.presave,
            "DeidExportReport_name": DeidExportReport.name,
            "table_configuration": self.custom_export.table_configuration,
            "domain": self.domain,
            "show_deid_column": show_deid_column(),
            'helper': {
                'back_url': self.ExportReport.get_url(domain=self.domain),
                'export_title': self.export_title,
                'slug': self.ExportReport.slug,
                'allow_deid': self.allow_deid
            }
        })


class FormCustomExportHelper(CustomExportHelper):

    ExportSchemaClass = FormExportSchema
    ExportReport = export.ExcelExportReport

    allow_deid = True

    @property
    def export_title(self):
        return _('Export Submissions to Excel')

    def __init__(self, request, domain, export_id=None):
        super(FormCustomExportHelper, self).__init__(request, domain, export_id)
        if not self.custom_export.app_id:
            self.custom_export.app_id = request.GET.get('app_id')

    def update_custom_params(self):
        p = self.post_data['custom_export']
        e = self.custom_export
        e.include_errors = p['include_errors']
        e.app_id = p['app_id']


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