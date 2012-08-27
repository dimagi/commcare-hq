from corehq.apps.data_interfaces.interfaces import DataInterface

class ImportCases(DataInterface):
    name = "Import Cases from Excel"
    slug = "import_cases"
    description = "Import case data from an external Excel file"
    report_template_path = "importer/import_cases.html"
    gide_filters = True
    asynchronous = False

    @property
    def report_context(self):
        error = self.request.GET.get("error", None)
        error_text=None
        if error == "nofile":
            error_text = 'Please choose an Excel file to import.'
        elif error == "file":
            error_text = 'The Excel file you chose could not be processed. Please check that it is saved as a Microsoft Excel 97/2000 .xls file.'
        elif error == "cases":
            error_text = 'No cases have been submitted to this domain. You cannot update case details from an Excel file until you have existing cases.'
        elif error == "cache":
            error_text = 'The session containing the file you uploaded has expired - please upload a new one.'
        return dict(
            error_text=error_text
        )

    @classmethod
    def show_in_navigation(cls, request, *args, **kwargs):
        user = request.couch_user
        domain = kwargs.get('domain')
        return user.is_superuser or user.is_previewer() or domain == 'khayelitsha'