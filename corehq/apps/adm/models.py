import logging
from couchdbkit.ext.django.schema import Document, StringProperty, ListProperty,\
    DocumentSchema, BooleanProperty, DictProperty, IntegerProperty, DateTimeProperty
import datetime
from django.utils.html import escape
from django.utils.safestring import mark_safe
from dimagi.utils.couch.database import get_db
from dimagi.utils.data.editable_items import InterfaceEditableItemMixin


FORM_KEY_TYPES = (('user', 'form.meta.user_id'))
CASE_KEY_TYPES = (('case_type', 'type'), ('project', 'domain'), ('user', 'user_id'))
KEY_TYPE_OPTIONS = [('user', "User"), ("case_type", "Case Type")]

REPORT_SECTION_OPTIONS = [("supervisor", "Supervisor Report")]

COLUMN_TYPES = ('form', 'case')

class ADMEditableItemMixin(InterfaceEditableItemMixin):

    def __getattr__(self, item):
        return super(ADMEditableItemMixin, self).__getattribute__(item)

    @property
    def editable_item_button(self):
        return """<a href="#updateADMItemModal"
        class="btn"
        data-item_id="%s"
        onclick="adm_interface.update_item(this)"
        data-toggle="modal"><i class="icon icon-pencil"></i> Edit</a>""" % self.get_id

    def _boolean_label(self, value, yes_text="Yes", no_text="No"):
        return mark_safe('<span class="label label-%s">%s</span>' %
                         ("success" if value else "warning", yes_text if value else no_text))

    def format_property(self, key, property):
        if isinstance(property, bool):
            return self._boolean_label(property)
        return super(ADMEditableItemMixin, self).format_property(key, property)

    def update_item(self, overwrite=True, **kwargs):
        for key, item in kwargs.items():
            try:
                setattr(self, key, item)
            except Exception as e:
                print "ERROR setting value for %s: %s" % (key, e)
        self.date_modified = datetime.datetime.utcnow()
        self.save()

    @classmethod
    def create_item(cls, overwrite=True, **kwargs):
        item = cls()
        item.update_item(**kwargs)
        return item


class ADMColumn(Document, ADMEditableItemMixin):
    """
        The basic ADM Column.
        Eventually, name and description will be user configurable.
        name, description, and couch_view are admin configurable
    """
    date_modified = DateTimeProperty()
    name = StringProperty(default="Untitled Column")
    description = StringProperty(default="")
    couch_view = StringProperty(default="")
    key_format = StringProperty(default="<domain>, <user_id>, <datespan>")
    base_doc = "ADMColumn"

    @property
    def row_columns(self):
        return ["name", "description", "couch_view", "key_format"]


    def format_property(self, key, property):
        if key == 'key_format':
            return '[%s]' % escape(property)
        if key == "name":
            return "%s [%s]" % (property, self.get_id)
        return super(ADMColumn, self).format_property(key, property)

#    def value(self, project, key_id,
#              startdate=None, enddate=None):
#        return ""
#
#    def format_display(self, key_id):
#        return ""
#
#    def _results(self, startdate, enddate):
#        return get_db().view(self._couch_view,
#
#        )

class ReducedADMColumn(ADMColumn):
    """
        Returns the value of the reduced view of whatever couch_view is specified.
        Generally used to retrieve countable items.

        duration_of_project:
        True -> do not pay attention to startdate and enddate when grabbing the reduced view.
        False -> return reduced view between startdate and enddate
    """
    returns_numerical = BooleanProperty(default=False)
    duration_of_project = BooleanProperty(default=False)

    @property
    def row_columns(self):
        cols = super(ReducedADMColumn, self).row_columns
        cols.append("returns_numerical")
        cols.append("duration_of_project")
        return cols

    def update_item(self, overwrite=True, **kwargs):
        self.duration_of_project = kwargs.get('duration_of_project', False)
        super(ReducedADMColumn, self).update_item(overwrite, **kwargs)

class DaysSinceADMColumn(ADMColumn):
    """
        The number of days since enddate <property_name>'s date.
        property_name should be a datetime.
    """
    returns_numerical = True
    property_name = StringProperty(default="")
    start_or_end = StringProperty(default="enddate")

    @property
    def row_columns(self):
        cols = super(DaysSinceADMColumn, self).row_columns
        cols.append("property_name")
        cols.append("start_or_end")
        return cols

    def format_property(self, key, property):
        if key == "start_or_end":
            from corehq.apps.adm.forms import DATESPAN_CHOICES
            choices = dict(DATESPAN_CHOICES)
            return "%s and %s" % (self.property_name, choices.get(property, "--"))
        return super(DaysSinceADMColumn, self).format_property(key, property)


class ConfigurableADMColumn(ADMColumn):
    """
        Use this for columns that will be end-user configurable.
        Default versions of this column, which are only superuser configurable, will have project = ""
    """
    project = StringProperty()
    directly_configurable = BooleanProperty(default=False)
    config_doc = "ConfigurableADMColumn"

    @property
    def row_columns(self):
        return ["name", "description", "couch_view", "key_format", "directly_configurable", "project"]

    @property
    def default_properties(self):
        return []

    @property
    def editable_item_button(self):
        return """<a href="#updateADMItemModal"
        class="btn"
        data-item_id="%s"
        data-form_class="%s"
        onclick="adm_interface.update_item(this)"
        data-toggle="modal"><i class="icon icon-pencil"></i> Edit</a>""" % \
               (self.get_id, "%sForm" % self.__class__.__name__)

    @property
    def default_properties_in_row(self):
        properties = ['<dl class="dl-horizontal" style="margin:0;padding:0;">']
        for key in self.default_properties:
            property = getattr(self, key)
            properties.append("<dt>%s</dt>" % self.format_key(key))
            properties.append("<dd>%s</dd>" % self.format_property(key, property))
        properties.append("</dl>")
        return mark_safe("\n".join(properties))

    def format_property(self, key, property):
        if key == 'project':
            return self.default_properties_in_row
        if key == "name":
            return '%s <br />[%s] <span class="label label-inverse">%s</span>' % \
                   (self.name, self.get_id, self.__class__.__name__)
        return super(ConfigurableADMColumn, self).format_property(key, property)

    def format_key(self, key):
        return key.replace("_", " ").title()

    @classmethod
    def all_configurable_columns(cls):
        couch_key = ["defaults"]
        data = get_db().view('adm/configurable_columns',
            reduce=False,
            startkey=couch_key,
            endkey=couch_key+[{}]
        ).all()
        wrapped_data = []
        for item in data:
            key = item.get('key', [])
            try:
                item_class = eval(key[1])
                wrapped_data.append(item_class.get(key[-1]))
            except Exception:
                pass
        return wrapped_data

class ADMCompareColumn(ConfigurableADMColumn):
    """
        This is a shell of a proposal when we decide to allow more generic, customizable ADM columns.
    """
    numerator_id = StringProperty() # takes the id of an ADMColumn
    denominator_id = StringProperty() # takes the id of an ADMVolumn

    @property
    def default_properties(self):
        return ["numerator_id", "denominator_id"]

    def format_key(self, key):
        if key == "numerator_id" or key == "denominator_id":
            return key.replace("_id", "").title()
        return super(ADMCompareColumn, self).format_key(key)

    def format_property(self, key, property):
        if key == "couch_view" or key == "key_format":
            return "N/A"
        if key == "numerator_id" or key == "denominator_id":
            try:
                print property
                col = ADMColumn.get(property)
                return col.name
            except Exception:
                return "Untitled Column"
        return super(ADMCompareColumn, self).format_property(key, property)

    @classmethod
    def numerical_column_options(cls):
        key = ["numerical"]
        data = get_db().view("adm/all_default_columns",
            reduce=False,
            startkey=key,
            endkey=key+[{}]
        ).all()

        return [("", "Select a Column")] + \
               [(item.get("key", [])[-1], item.get("value", {}).get("name", "Untitled"))
                        for item in data]


class InactiveADMColumn(ConfigurableADMColumn):
    """
        Cases that are still open but date_modified is older than <inactivity_milestone> days from the
        enddate of the report.

        Returns the reduced value of whatever couch_view is specified, and keys from:
        [domain, key_type_id] to [domain, key_type_id, enddate-<inactivity_milestone> days]

    """
    returns_numerical = True
    inactivity_milestone = IntegerProperty()

    @property
    def default_properties(self):
        return ["inactivity_milestone"]

    def format_property(self, key, property):
        if key == 'inactivity_milestone':
            return "%s days" % property
        return super(InactiveADMColumn, self).format_property(key, property)


class ADMReport(Document, ADMEditableItemMixin):
    name = StringProperty(default="Untitled Report")
    description = StringProperty(default="")
    slug = StringProperty(default="untitled")
    reporting_section = StringProperty(default="supervisor")
    column_ids = ListProperty() # list of column ids
    key_type = StringProperty(default="user")
    project = StringProperty()

    @property
    def row_columns(self):
        return ["reporting_section", "name", "description", "slug", "columns", "key_type"]

    @property
    def columns(self):
        return ",".join(self.column_ids)

    def update_item(self, overwrite=True, **kwargs):
        kwargs['column_ids'] = kwargs.get('columns', [])
        super(ADMReport, self). update_item(overwrite, **kwargs)

    def format_property(self, key, property):
        if key == 'columns':
            col_names = []
            for col_id in self.column_ids:
                try:
                    col = ADMColumn.get(col_id)
                    col_names.append(col.name)
                except Exception:
                    col_names.append(col_id)
            return "[%s]" % ", ".join(col_names)
        if key == 'reporting_section':
            sections = dict(REPORT_SECTION_OPTIONS)
            return sections.get(property, "Unknown")
        return super(ADMReport, self).format_property(key, property)

