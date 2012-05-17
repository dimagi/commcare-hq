from corehq.apps.reports.custom import HQReport

class ExcelImporter(HQReport):
    name = "Import data from Excel"
    slug = "excel_import"
    description = "Import case data from an external Excel file"
    template_name = "excel_import.html"
    fields = []
    
    def calc(self):
        error = self.request.GET.get("error", None)
        
        if error == "nofile":
            self.context['error_text'] = 'Please choose an Excel file to import.'
        elif error == "file":
            self.context['error_text'] = 'The Excel file you chose could not be processed. Please check that it is saved as a Microsoft Excel 97/2000 .xls file.'
        elif error == "cases":
            self.context['error_text'] = 'No cases have been submitted to this domain. You cannot update case details from an Excel file until you have existing cases.'            
