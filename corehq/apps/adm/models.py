from couchdbkit.ext.django.schema import Document, StringProperty, ListProperty,\
    DocumentSchema, BooleanProperty, DictProperty, IntegerProperty, DateTimeProperty
import datetime
from django.utils.html import escape
from django.utils.safestring import mark_safe
from dimagi.utils.couch.database import get_db
from dimagi.utils.data.editable_items import InterfaceEditableItemMixin


FORM_KEY_TYPES = (('user', 'form.meta.user_id'))
CASE_KEY_TYPES = (('case_type', 'type'), ('project', 'domain'), ('user', 'user_id'))
KEY_TYPES = ('user', 'case_type')

COLUMN_TYPES = ('form', 'case')


class ADMColumn(Document, InterfaceEditableItemMixin):
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
    def editable_item_button(self):
        return """<a href="#updateADMItemModal"
        class="btn"
        data-item_id="%s"
        onclick="adm_interface.update_item(this)"
        data-toggle="modal"><i class="icon icon-pencil"></i> Edit</a>""" % self.get_id

    @property
    def row_columns(self):
        return ["name", "description", "couch_view", "key_format"]

    def _boolean_label(self, value, yes_text="Yes", no_text="No"):
        return mark_safe('<span class="label label-%s">%s</span>' %
                         ("success" if value else "warning", yes_text if value else no_text))


    def format_property(self, key, property):
        if key == 'key_format':
            return '[%s]' % escape(property)
        if isinstance(property, bool):
            return self._boolean_label(property)
        return super(ADMColumn, self).format_property(key, property)

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
    config_doc = "ConfigurableADMColumn"

class ADMCompareColumn(ConfigurableADMColumn):
    """
        This is a shell of a proposal when we decide to allow more generic, customizable ADM columns.
    """
    numerator_id = StringProperty() # takes the id of an ADMColumn
    denominator_id = StringProperty() # takes the id of an ADMVolumn

class InactiveADMColumn(ConfigurableADMColumn):
    """
        Cases that are still open but date_modified is older than <inactivity_milestone> days from the
        enddate of the report.

        Returns the reduced value of whatever couch_view is specified, and keys from:
        [domain, key_type_id] to [domain, key_type_id, enddate-<inactivity_milestone> days]

    """
    inactivity_milestone = IntegerProperty()

class ADMReport(Document):
    columns = ListProperty() # list of column ids
    key_type = StringProperty()
    project = StringProperty()