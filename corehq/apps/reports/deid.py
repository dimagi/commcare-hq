from corehq.apps.reports.standard import ExcelExportReport

class FormDeidExport(ExcelExportReport):
    slug = 'form_deid_export'
    name = "De-Identified Export"
    template_name = 'reports/reportdata/form_deid_export.html'
    def calc(self):
        self.context.update({
            'saved_exports': self.get_saved_exports(),
            'get_filter_params': self.get_filter_params(),
        })
