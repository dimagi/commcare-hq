from couchdbkit.ext.django.schema import Document, StringProperty, ListProperty,\
    DocumentSchema, BooleanProperty, DictProperty, IntegerProperty, DateTimeProperty
import datetime
import dateutil
from django.utils.html import escape
from django.utils.safestring import mark_safe
import pytz
from casexml.apps.case.models import CommCareCase
from corehq.apps.adm import utils
from corehq.apps.groups.models import Group
from dimagi.utils.couch.database import get_db
from dimagi.utils.data.editable_items import InterfaceEditableItemMixin
from dimagi.utils.dates import DateSpan
from dimagi.utils.modules import to_function
from dimagi.utils.timezones import utils as tz_utils
from corehq.apps.users.models import CommCareUser
from copy import copy


KEY_TYPE_OPTIONS = [('user_id', "User"), ("case_type", "Case Type")]
REPORT_SECTION_OPTIONS = [("supervisor", "Supervisor Report")]
COLUMN_TYPES = ('form', 'case')
CASE_FILTER_OPTIONS = [
    ('', "Use all case types"),
    ('in', 'Use only the case types specified below'),
    ('ex', 'Use all case types except for those specified below')
]
CASE_STATUS_OPTIONS = [
    ('', 'All Cases'),
    ('open', 'Open Cases'),
    ('closed', 'Closed Cases')
]


class ADMEditableItemMixin(InterfaceEditableItemMixin):

    def __getattr__(self, item):
        return super(ADMEditableItemMixin, self).__getattribute__(item)

    @property
    def editable_item_button(self):
        return mark_safe("""<a href="#updateADMItemModal"
        class="btn"
        data-item_id="%s"
        onclick="adm_interface.update_item(this)"
        data-toggle="modal"><i class="icon icon-pencil"></i> Edit</a>""" % self.get_id)

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
    """
    name = StringProperty(default="Untitled Column")
    description = StringProperty(default="")
    slug = StringProperty(default="")

    date_modified = DateTimeProperty()
    base_doc = "ADMColumn"

    _report_datespan = None
    @property
    def report_datespan(self):
        """
            The value for the datespan filter from the report accessing this ADMColumn. This should either return
            None if a datespan was not set by the report (odd) or a DateSpan object.
            You care about:
            - datespan.startdate
            - datespan.enddate
        """
        return self._report_datespan

    _report_domain = None
    @property
    def report_domain(self):
        """
            The name of the domain accessing this ADM report.

            NOTE:
            If you are using a ConfigurableADMColumn subclass, do not confuse this with 'domain'!
            ConfigurableADMColumn.domain refers to the domain that that column definition
            applies to. A default ADMColumn that applies to all domains will have domain == ''.
            When a user modifies a property for that ConfigurableADMColumn then that saved modified column
            definition will have the domain set.
        """
        return self._report_domain

    @property
    def row_columns(self):
        return ["slug", "name", "description"]

    def set_report_values(self, **kwargs):
        """
            This is called when rendering ADM report. Insert any relevant filters here.
        """
        datespan = kwargs.get('datespan')
        self._report_datespan = datespan if isinstance(datespan, DateSpan) else None
        domain = kwargs.get('domain')
        self._report_domain = domain

    def format_property(self, key, property):
        if key == "name":
            return "%s" % property
        return super(ADMColumn, self).format_property(key, property)

    def raw_value(self, **kwargs):
        raise NotImplementedError

    def clean_value(self, value):
        return value

    def html_value(self, value):
        return value

    @classmethod
    def get_col(cls, col_id):
        try:
            column_doc = get_db().get(col_id)
            column_class = column_doc.get('doc_type')
            column = to_function('corehq.apps.adm.%s' % column_class)
            column = column.wrap(column_doc)
            return column
        except Exception as e:
            return None

    @classmethod
    def default_by_slug(cls, slug, domain=None):
        key = [domain, slug]
        couch_view = 'adm/all_default_columns'
        column = None

        if domain:
            prefix = ["defaults domain slug"]
            column = get_db().view(couch_view,
                startkey=prefix+key,
                endkey=prefix+key+[{}],
                reduce=False
            ).first()

        if not column:
            prefix = ["defaults global slug"]
            column = get_db().view(couch_view,
                startkey=prefix+key,
                endkey=prefix+key+[{}],
                reduce=False
            ).first()
        if column:
            return cls.get_col(column.get('id'))
        return None


class CouchViewADMColumn(ADMColumn):
    """
        Use this for generic columns that pull data straight from specific couch views.
    """
    couch_view = StringProperty(default="")
    key_format = StringProperty(default="<domain>, <user_id>, <datespan>")
    
    @property
    def row_columns(self):
        return super(CouchViewADMColumn, self).row_columns + \
               ["couch_view", "key_format"]

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

    _key_kwargs = None
    @property
    def key_kwargs(self):
        if self._key_kwargs is None:
            self._key_kwargs = {u'{}': {}}
        return self._key_kwargs

    def set_report_values(self, **kwargs):
        super(CouchViewADMColumn, self).set_report_values(**kwargs)
        self.key_kwargs.update(self._format_keywords_in_kwargs(**kwargs))

    def _format_keywords_in_kwargs(self, **kwargs):
        return dict([("<%s>" % k, v) for k, v in kwargs.items()])

    def format_property(self, key, property):
        if key == 'key_format':
            return '[%s]' % escape(property)
        return super(CouchViewADMColumn, self).format_property(key, property)

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
        return self.get_couch_view_data(cleaned_key, datespan)

    def get_couch_view_data(self, key, datespan=None):
        data = self.view_results(**utils.standard_start_end_key(key, datespan))
        return data.all() if data else None

    def view_results(self, reduce=False, **kwargs):
        try:
            data = get_db().view(self.couch_view,
                reduce=reduce,
                **kwargs
            )
        except Exception as e:
            data = None
        return data

    @property
    def is_user_column(self):
        # a bit of a hack - used for determining if this refers to users
        return "<user_id>" in self.key_format
        
    def _expand_user_key(self, key):
        # given a formatted key, expand it by including all the 
        # owner ids
        index = self.couch_key.index("<user_id>")
        user_id = key[index]
        def _repl(k, index, id):
            ret = copy(k)
            ret[index] = id
            return ret
        return [_repl(key, index, id) for id in CommCareUser.get(user_id).get_owner_ids()]


class ReducedADMColumn(CouchViewADMColumn):
    """
        Returns the value of the reduced view of whatever couch_view is specified.
        Generally used to retrieve countable items.

        ignore_datespan:
        True -> do not filter view by the stardate and enddate
        False -> filter the view by the startdate and enddate
    """
    returns_numerical = BooleanProperty(default=False)
    ignore_datespan = BooleanProperty(default=False)

    @property
    def row_columns(self):
        cols = super(ReducedADMColumn, self).row_columns
        cols.append("returns_numerical")
        cols.append("ignore_datespan")
        return cols

    def aggregate(self, values):
        return reduce(lambda x, y: x+ y, values) if self.returns_numerical \
            else ', '.join(values)
    
    def update_item(self, overwrite=True, **kwargs):
        self.ignore_datespan = kwargs.get('ignore_datespan', False)
        super(ReducedADMColumn, self).update_item(overwrite, **kwargs)

    def get_couch_view_data(self, key, datespan=None):
        if self.ignore_datespan:
            datespan = None
        # for now, if you're working with users assume you use all
        # their owner ids in your query
        keys = [key] if not self.is_user_column else self._expand_user_key(key)
        def _val(key, datespan): 
            start_end = utils.standard_start_end_key(key, datespan)
            data = self.view_results(reduce=True, **start_end).first()
            value = data.get('value', 0) if data \
                else 0 if self.returns_numerical else None
            return value
        return self.aggregate(_val(k, datespan) for k in keys)


class DaysSinceADMColumn(CouchViewADMColumn):
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

    def get_couch_view_data(self, key, datespan=None):
        default_value = None
        try:
            now = tz_utils.adjust_datetime_to_timezone(getattr(datespan, self.start_or_end or "enddate"),
                from_tz=datespan.timezone, to_tz=pytz.utc)
        except Exception:
            now = datetime.datetime.now(tz=pytz.utc)
        data = self.view_results(
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
    """
    is_default = BooleanProperty(default=True)
    domain = StringProperty()
    directly_configurable = BooleanProperty(default=False)
    based_on_column = StringProperty()
    config_doc = "ConfigurableADMColumn"

    @property
    def row_columns(self):
        return super(ConfigurableADMColumn, self).row_columns + \
               ["domain", "directly_configurable", "is_default"]

    @property
    def default_properties(self):
        return []

    @property
    def editable_item_button(self):
        return mark_safe("""<a href="#updateADMItemModal"
        class="btn"
        data-item_id="%s"
        data-form_class="%s"
        onclick="adm_interface.update_item(this)"
        data-toggle="modal"><i class="icon icon-pencil"></i> Edit</a>""" % \
               (self.get_id, "%sForm" % self.__class__.__name__))

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
        if key == 'domain':
            return property if property else "For All Projects"
        if key == 'is_default':
            return self.default_properties_in_row
        if key == "name":
            return mark_safe('%s<br /><span class="label label-inverse">%s</span>' % \
                   (self.name, self.__class__.__name__))
        return super(ConfigurableADMColumn, self).format_property(key, property)

    def format_key(self, key):
        return key.replace("_", " ").title()

    @classmethod
    def all_admin_configurable_columns(cls):
        couch_key = ["defaults all type"]
        data = get_db().view('adm/configurable_columns',
            reduce=False,
            startkey=couch_key,
            endkey=couch_key+[{}]
        ).all()
        wrapped_data = []
        for item in data:
            key = item.get('key', [])
            value = item.get('value', {})
            try:
                item_class = to_function("corehq.apps.adm.models.%s" % value.get('type', 'ADMColumn'))
                wrapped_data.append(item_class.get(key[-1]))
            except Exception as e:
                print "EXCEPTION", e
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

    def set_report_values(self, **kwargs):
        super(ADMCompareColumn, self).set_report_values(**kwargs)
        if self.numerator:
            self.numerator.set_report_values(**kwargs)
        if self.denominator:
            self.denominator.set_report_values(**kwargs)

    def format_key(self, key):
        if key == "numerator_id" or key == "denominator_id":
            return key.replace("_id", "").title()
        return super(ADMCompareColumn, self).format_key(key)

    def format_property(self, key, property):
        if key == "numerator_id" or key == "denominator_id":
            try:
                col = ADMColumn.get(property)
                return "%s (%s)" % (col.name, col.domain if hasattr(col, 'domain') and col.domain else 'Any Project')
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
        n = value.get('numerator', 0)
        try:
            return float(n)/float(d)
        except Exception:
            return 0

    def html_value(self, value):
        default_value = "--"
        d = value.get('denominator', 0)
        if d<= 0:
            return default_value
        n = value.get('numerator', 0)
        try:
            return "%d/%d (%.f%%)" % (n, d, float(n)/float(d)*100)
        except Exception:
            return default_value

    @classmethod
    def numerical_column_options(cls):
        key = ["numerical"]
        data = get_db().view("adm/all_default_columns",
            reduce=False,
            startkey=key,
            endkey=key+[{}]
        ).all()
        return [("", "Select a Column")] + \
               [(item.get("key", [])[-1],
                 "%s (%s)" % (item.get("value", {}).get("name", "Untitled"),
                              item.get("value", {}).get("domain", "Any Project"))
                   )
                        for item in data]


class CaseFilterADMColumnMixin(DocumentSchema):
    """
        Use this mixin when you want to filter the results by case_types.
        Assumes that the result returned will be a list of CommCareCases.
    """
    filter_option = StringProperty(default='', choices=[f[0] for f in CASE_FILTER_OPTIONS])
    case_types = ListProperty()
    case_status = StringProperty(default='', choices=[s[0] for s in CASE_STATUS_OPTIONS])

    def format_case_filter_properties(self, key, property):
        if key == 'filter_option':
            filter_options = dict(CASE_FILTER_OPTIONS)
            return filter_options[property or '']
        if key == 'case_types':
            return ", ".join(property) if property else 'N/A'
        return None

    def get_filtered_cases(self, domain, user_id, include_groups=True, status=None, include_docs=False, datespan_keys=None):
        if not datespan_keys:
            datespan_keys = [[], [{}]]

        owner_ids = [user_id]
        if include_groups:
            groups = Group.by_user(user_id, wrap=False)
            owner_ids.extend(groups)

        pass_filter_types = self.case_types if self.filter_option == CASE_FILTER_OPTIONS[1][0] else [None]

        all_cases = list()
        for case_type in pass_filter_types:
            for owner in owner_ids:
                data = self._cases_by_type(domain, owner, case_type, status=status,
                    include_docs=include_docs, datespan_keys=datespan_keys)
                all_cases.extend(data)
        if self.filter_option == CASE_FILTER_OPTIONS[2][0]:
            filtered_cases = list()
            for case in all_cases:
                case_type = case.type if include_docs else case.get('value', {}).get('type')
                print "CASE TYPE", case_type
                if case_type in self.case_types:
                    filtered_cases.append(case)
            all_cases = filtered_cases
        return all_cases

    def _cases_by_type(self, domain, owner_id, case_type, status=None, include_docs=False, datespan_keys=None):
        couch_key = [domain, {}, {}, owner_id]
        if case_type:
            couch_key[2] = case_type
        if status:
            couch_key[1] = status
        return CommCareCase.view('case/by_date_modified_owner',
            reduce=False,
            startkey=couch_key+datespan_keys[0],
            endkey=couch_key+datespan_keys[1],
            include_docs=include_docs
        ).all()


class CaseCountADMColumn(ConfigurableADMColumn, CaseFilterADMColumnMixin):
    """
        Cases that are still open but date_modified is older than <inactivity_milestone> days from the
        enddate of the report.

    """
    returns_numerical = True
    inactivity_milestone = IntegerProperty(default=0)
    ignore_datespan = BooleanProperty(default=True)

    @property
    def default_properties(self):
        return ["case_status", "filter_option", "case_types", "inactivity_milestone", "ignore_datespan"]

    def format_property(self, key, property):
        if key == 'inactivity_milestone':
            return "%s days" % property
        case_filter_props = self.format_case_filter_properties(key, property)
        if case_filter_props is not None:
            return case_filter_props
        return super(CaseCountADMColumn, self).format_property(key, property)

    def raw_value(self, **kwargs):
        user_id = kwargs.get('user_id')
        print "USER ID", user_id
        datespan_keys = None
        if self.inactivity_milestone > 0:
            milestone_days_ago = tz_utils.adjust_datetime_to_timezone(self.report_datespan.enddate,
                from_tz=self.report_datespan.timezone, to_tz=pytz.utc) - datetime.timedelta(days=self.inactivity_milestone)
            datespan_keys = [[], [milestone_days_ago.isoformat()]]
        elif not self.ignore_datespan:
            datespan_keys = [[self.report_datespan.startdate_param_utc], [self.report_datespan.enddate_param_utc]]
        status = self.case_status if self.case_status else None
        cases = self.get_filtered_cases(self.report_domain, user_id, status=status, datespan_keys=datespan_keys)
        return len(cases) if isinstance(cases, list) else None

    def clean_value(self, value):
        return value if value is not None else 0

    def html_value(self, value):
        return value if value is not None else "--"


class CaseCountADMColumn(ConfigurableADMColumn, CaseFilterADMColumnMixin):
    """
        Count of all cases.
    """
    returns_numerical = True

    @property
    def default_properties(self):
        return ["ignore_datespan", "filter_option", "case_types"]

    def format_property(self, key, property):
        case_filter_props = self.format_case_filter_properties(key, property)
        if case_filter_props is not None:
            return case_filter_props
        return super(CaseCountADMColumn, self).format_property(key, property)

    def raw_value(self, **kwargs):
        user_id = kwargs.get('user_id')
        datespan_keys = None if self.ignore_datespan else \
                    [[self.report_datespan.startdate_param_utc], [self.report_datespan.enddate_param_utc]]
        cases = self.get_filtered_cases(self.report_domain, user_id, datespan_keys=datespan_keys)
        return len(cases) if isinstance(cases, list) else None

#    def update_item(self, overwrite=True, **kwargs):
#        kwargs['case_types'] = kwargs.get('case_types', [])
#        super(CaseCountADMColumn, self).update_item(overwrite, **kwargs)

    def clean_value(self, value):
        return value if value is not None else 0

    def html_value(self, value):
        return value if value is not None else "--"


class ADMReport(Document, ADMEditableItemMixin):
    name = StringProperty(default="Untitled Report")
    description = StringProperty(default="")
    slug = StringProperty(default="untitled")

    reporting_section = StringProperty(default="supervisor")
    column_slugs = ListProperty() # list of column ids
    key_type = StringProperty(default="user_id")
    is_default = BooleanProperty(default=True)
    domain = StringProperty()
    based_on_report = StringProperty()

    @property
    def row_columns(self):
        return ["reporting_section", "name", "description", "slug", "column_slugs", "key_type"]

    _columns = None
    @property
    def columns(self):
        if self._columns is None:
            cols = []
            for slug in self.column_slugs:
                column = ADMColumn.default_by_slug(slug, self.viewing_domain)
                if column:
                    cols.append(column)
            self._columns = cols
        return self._columns

    _viewing_domain = None
    @property
    def viewing_domain(self):
        """
            The domain that is viewing this report.
        """
        if _viewing_domain is None:
            self._viewing_domain = self.domain
        return self._viewing_domain

    def set_domain_specific_values(self, **kwargs):
        domain = kwargs.get('domain')
        self._viewing_domain = domain

    def format_property(self, key, property):
        if key == 'column_slugs':
            return  ", ".join(property)
        if key == 'reporting_section':
            sections = dict(REPORT_SECTION_OPTIONS)
            return sections.get(property, "Unknown")
        return super(ADMReport, self).format_property(key, property)

