from django.utils.safestring import mark_safe
from corehq.apps.adm.admin import BaseADMAdminInterface
from corehq.apps.adm.admin.forms import CouchViewADMColumnForm, ReducedADMColumnForm, \
    DaysSinceADMColumnForm, ConfigurableADMColumnChoiceForm
from corehq.apps.adm.models import ReducedADMColumn, DaysSinceADMColumn, ConfigurableADMColumn
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn

class BaseADMColumnAdminInterface(BaseADMAdminInterface):
    crud_item_type = "Column"

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Slug"),
            DataTablesColumn("Project"),
            DataTablesColumn("Column Name"),
            DataTablesColumn("Description"),
            DataTablesColumn("Edit"),
        )

    @property
    def rows(self):
        rows = []
        for item in self.columns:
            rows.append(item.admin_crud.row)
        return rows

    @property
    def columns(self):
        key = ["defaults all type", self.document_class.__name__]
        data = self.document_class.view('adm/all_default_columns',
            reduce=False,
            include_docs=True,
            startkey=key,
            endkey=key+[{}]
        ).all()
        return data


class CouchViewADMColumnAdminInterface(BaseADMColumnAdminInterface):
    crud_item_type = "Couch View Column"
    form_class = CouchViewADMColumnForm

    @property
    def headers(self):
        header = super(CouchViewADMColumnAdminInterface, self).headers
        header.insert_column(DataTablesColumn("Couch View"), -1)
        header.insert_column(DataTablesColumn("Key Format"), -1)
        return header


class ReducedADMColumnInterface(CouchViewADMColumnAdminInterface):
    name = "Reduced & Unfiltered ADMCol"
    description = "Typically used for ADM Columns displaying a count (No. Cases or No. Submissions)."
    slug = "reduced_column"
    document_class = ReducedADMColumn
    form_class = ReducedADMColumnForm

    crud_item_type = "Reduced ADM Column"
    detailed_description = mark_safe("""<p>This column returns the reduced value of the couch_view specified. This assumes that
    the reduced view returns a numerical value.</p>
    <p><strong>Example Usage:</strong> Columns that display a count, like # Cases or # Submissions.</p>""")

    @property
    def headers(self):
        header = super(ReducedADMColumnInterface, self).headers
        header.insert_column(DataTablesColumn("Returns a Number"), -1)
        header.insert_column(DataTablesColumn("Dates Span Duration of Project"), -1)
        return header


class DaysSinceADMColumnInterface(CouchViewADMColumnAdminInterface):
    name = "Days Since ADM Column"
    description = "Columns that return the number of days since the specified datetime property occurred."
    slug = "days_since_column"
    document_class = DaysSinceADMColumn
    form_class = DaysSinceADMColumnForm

    crud_item_type = "Days Since ADM Column"
    detailed_description = mark_safe("""<p>Returns the number of days between the date of
    <span class="label">property_name</span> of the first item in the view and the
    startdate or enddate of the datespan.</p>""")

    @property
    def headers(self):
        header = super(DaysSinceADMColumnInterface, self).headers
        header.insert_column(DataTablesColumn("Property Name"), -1)
        header.insert_column(DataTablesColumn("Returns No. Days Between"), -1)
        return header


class ConfigurableADMColumnInterface(BaseADMColumnAdminInterface):
    name = "Configurable ADM Columns"
    description = "Default definitions for configurable ADM Columns"
    slug = "config_column"
    document_class = ConfigurableADMColumn
    form_class = ConfigurableADMColumnChoiceForm

    crud_item_type = "User-Configurable ADM Column"

    @property
    def headers(self):
        header = super(ConfigurableADMColumnInterface, self).headers
        header.insert_column(DataTablesColumn("Type"), 0)
        header.insert_column(DataTablesColumn("Directly Configurable"), -1)
        header.insert_column(DataTablesColumn("Default Configurable Properties"), -1)
        return header

    @property
    def columns(self):
        return self.document_class.all_admin_configurable_columns()
