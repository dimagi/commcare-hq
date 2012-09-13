import logging
import re
from couchdbkit.ext.django.schema import Document, StringProperty, ListProperty,\
    DocumentSchema, BooleanProperty, DictProperty, IntegerProperty, DateTimeProperty
import datetime
import dateutil
from django.utils.html import escape
from django.utils.safestring import mark_safe
import pytz
from dimagi.utils.couch.database import get_db
from dimagi.utils.data.editable_items import InterfaceEditableItemMixin
from dimagi.utils.dates import DateSpan
from dimagi.utils.modules import to_function
from dimagi.utils.timezones import utils as tz_utils


FORM_KEY_TYPES = (('user_id', 'form.meta.user_id'))
CASE_KEY_TYPES = (('case_type', 'type'), ('project', 'domain'), ('user_id', 'user_id'))
KEY_TYPE_OPTIONS = [('user_id', "User"), ("case_type", "Case Type")]

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
            except AttributeError:
                pass
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

    _couch_key = None
    @property
    def couch_key(self):
        if self._couch_key is None:
            keys = self.key_format.split(",")
            key_vals = []
            for key in keys:
                key = key.strip()
                key_vals.append(self.key_kwargs.get(key, key))
            self._couch_key = key_vals
        return self._couch_key

    _key_kwargs = dict()
    @property
    def key_kwargs(self):
        return self._key_kwargs

    def _format_keywords_in_kwargs(self, **kwargs):
        return dict([("<%s>" % k, v) for k, v in kwargs.items()])

    def set_key_kwargs(self, **kwargs):
        self._key_kwargs = {u'{}': {}}
        self._key_kwargs.update(self._format_keywords_in_kwargs(**kwargs))

    def format_property(self, key, property):
        if key == 'key_format':
            return '[%s]' % escape(property)
        if key == "name":
            return "%s [%s]" % (property, self.get_id)
        return super(ADMColumn, self).format_property(key, property)

    def raw_value(self, **kwargs):
        kwargs = self._format_keywords_in_kwargs(**kwargs)
        cleaned_key = []
        datespan = None
        for key in self.couch_key:
            if isinstance(key, DateSpan):
                datespan = key
            elif isinstance(key, str) or isinstance(key, unicode):
                cleaned_key.append(kwargs.get(key, key))
            else:
                cleaned_key.append(key)
        return self.get_data(cleaned_key, datespan)

    def clean_value(self, value):
        return value

    def html_value(self, value):
        return value

    def get_data(self, key, datespan=None):
        data = self.get_view_results(**self.standard_start_end(key, datespan))
        return data.all() if data else None

    def get_view_results(self, reduce=False, **kwargs):
        try:
            data = get_db().view(self.couch_view,
                reduce=reduce,
                **kwargs
            )
        except Exception as e:
            data = None
        return data

    def standard_start_end(self, key, datespan=None):
        startkey_suffix = [datespan.startdate_param_utc] if datespan else []
        endkey_suffix = [datespan.enddate_param_utc] if datespan else [{}]
        return dict(
            startkey=key+startkey_suffix,
            endkey=key+endkey_suffix
        )

    @classmethod
    def get_col(cls, col_id):
        try:
            column_doc = get_db().get(col_id)
            column_class = column_doc.get('doc_type')
            column = eval(column_class)
            column = column.wrap(column_doc)
            return column
        except Exception as e:
            return None


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

    def get_data(self, key, datespan=None):
        if self.duration_of_project:
            datespan = None
        start_end = self.standard_start_end(key, datespan)
        value = 0 if self.returns_numerical else None
        data = self.get_view_results(reduce=True, **start_end).first()
        if data:
            value = data.get('value', 0)
        return value


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

    def _get_property_from_doc(self, doc, property):
        if isinstance(doc, dict) and len(property) > 0:
            return self._get_property_from_doc(doc.get(property[0]), property[1:-1])
        return doc

    def format_property(self, key, property):
        if key == "start_or_end":
            from corehq.apps.adm.forms import DATESPAN_CHOICES
            choices = dict(DATESPAN_CHOICES)
            return "%s and %s" % (self.property_name, choices.get(property, "--"))
        return super(DaysSinceADMColumn, self).format_property(key, property)

    def get_data(self, key, datespan=None):
        default_value = None
        try:
            now = tz_utils.adjust_datetime_to_timezone(getattr(datespan, self.start_or_end or "enddate"),
                from_tz=datespan.timezone, to_tz=pytz.utc)
        except Exception:
            now = datetime.datetime.now(tz=pytz.utc)
        data = self.get_view_results(
            endkey=key,
            startkey=key+[getattr(datespan, "%s_param_utc" % self.start_or_end)] if datespan else [{}],
            descending=True,
            include_docs=True
        )
        if not data:
            return default_value
        data = data.first()
        if not data:
            return default_value
        doc = data.get('doc', {})
        date_property = self._get_property_from_doc(doc, self.property_name.split('.'))
        try:
            date_property = dateutil.parser.parse(date_property)
            if not isinstance(date_property, datetime.datetime):
                return default_value
            td = now - date_property
            days = td.days
        except Exception:
            return default_value
        return days if days > 0 else 0

    def clean_value(self, value):
        return value if value >= 0 else -1

    def html_value(self, value):
        return "%s" % value if value is not None else "--"


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
    numerator_id = StringProperty(default="") # takes the id of an ADMColumn
    denominator_id = StringProperty(default="") # takes the id of an ADMVolumn

    @property
    def default_properties(self):
        return ["numerator_id", "denominator_id"]

    _numerator = None
    @property
    def numerator(self):
        if self._numerator is None:
            self._numerator = ADMColumn.get_col(self.numerator_id)
        return self._numerator

    _denominator = None
    @property
    def denominator(self):
        if self._denominator is None:
            self._denominator = ADMColumn.get_col(self.denominator_id)
        return self._denominator

    def set_key_kwargs(self, **kwargs):
        super(ADMCompareColumn, self).set_key_kwargs(**kwargs)
        if self.numerator:
            self.numerator.set_key_kwargs(**kwargs)
        if self.denominator:
            self.denominator.set_key_kwargs(**kwargs)

    def format_key(self, key):
        if key == "numerator_id" or key == "denominator_id":
            return key.replace("_id", "").title()
        return super(ADMCompareColumn, self).format_key(key)

    def format_property(self, key, property):
        if key == "couch_view" or key == "key_format":
            return "N/A"
        if key == "numerator_id" or key == "denominator_id":
            try:
                col = ADMColumn.get(property)
                return col.name
            except Exception:
                return "Untitled Column"
        return super(ADMCompareColumn, self).format_property(key, property)

    def raw_value(self, **kwargs):
        numerator_raw = self.numerator.raw_value(**kwargs)
        denominator_raw = self.denominator.raw_value(**kwargs)
        return dict(
            numerator=self.numerator.clean_value(numerator_raw),
            denominator=self.denominator.clean_value(denominator_raw),
        )

    def clean_value(self, value):
        d = value.get('denominator', 0)
        if d <= 0:
            return d
        n = value.get('numerator', 0)
        return float(n)/float(d)

    def html_value(self, value):
        d = value.get('denominator', 0)
        if d<= 0:
            return "--"
        n = value.get('numerator', 0)
        return "%d/%d (%.2f%%)" % (n, d, float(n)/float(d)*100)


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

    def get_data(self, key, datespan=None):
        default_value = None

        return 0


class ADMReport(Document, ADMEditableItemMixin):
    name = StringProperty(default="Untitled Report")
    description = StringProperty(default="")
    slug = StringProperty(default="untitled")
    reporting_section = StringProperty(default="supervisor")
    column_ids = ListProperty() # list of column ids
    key_type = StringProperty(default="user_id")
    project = StringProperty()

    @property
    def row_columns(self):
        return ["reporting_section", "name", "description", "slug", "column_list", "key_type"]

    @property
    def column_list(self):
        return ",".join(self.column_ids)

    _columns = None
    @property
    def columns(self):
        if self._columns is None:
            cols = []
            for col_id in self.column_ids:
                column = ADMColumn.get_col(col_id)
                if column:
                    cols.append(column)
            self._columns = cols
        return self._columns

    def update_item(self, overwrite=True, **kwargs):
        kwargs['column_ids'] = kwargs.get('column_list', [])
        super(ADMReport, self). update_item(overwrite, **kwargs)

    def format_property(self, key, property):
        if key == 'column_list':
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

