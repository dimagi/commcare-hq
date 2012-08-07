from corehq.apps.data_interfaces.interfaces import DataInterface
from corehq.apps.reports.custom import HQReport

class ImportCases(DataInterface):
    name = "Import Cases from Excel"
    slug = "import_cases"
    description = "Import case data from an external Excel file"
    template_name = "importer/import_cases.html"
    fields = []
    asynchronous = False

    def calc(self):
        error = self.request.GET.get("error", None)
        
        if error == "nofile":
            self.context['error_text'] = 'Please choose an Excel file to import.'
        elif error == "file":
            self.context['error_text'] = 'The Excel file you chose could not be processed. Please check that it is saved as a Microsoft Excel 97/2000 .xls file.'
        elif error == "cases":
            self.context['error_text'] = 'No cases have been submitted to this domain. You cannot update case details from an Excel file until you have existing cases.'            
        elif error == "cache":
            self.context['error_text'] = 'The session containing the file you uploaded has expired - please upload a new one.'

    @classmethod
    def show_in_list(cls, domain, user):
        return user.is_superuser or user.is_previewer() or domain == 'khayelitsha'