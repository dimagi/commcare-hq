from corehq.apps.data_interfaces.interfaces import DataInterface

class ImportCases(DataInterface):
    name = "Import Cases from Excel"
    slug = "import_cases"
    description = "Import case data from an external Excel file"
    report_template_path = "importer/import_cases.html"
    gide_filters = True
    asynchronous = False

    @classmethod
    def show_in_navigation(cls, request, *args, **kwargs):
        user = request.couch_user
        domain = kwargs.get('domain')
        return user.is_superuser or user.is_previewer() or domain == 'khayelitsha'