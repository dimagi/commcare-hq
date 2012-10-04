import logging
from new import instancemethod
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
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.modules import to_function
from dimagi.utils.timezones import utils as tz_utils
from corehq.apps.users.models import CommCareUser
from copy import copy

KEY_TYPE_OPTIONS = [('user_id', "User"), ("case_type", "Case Type")]
REPORT_SECTION_OPTIONS = [("supervisor", "Supervisor Report")]
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

class NumericalADMColumnMixin(DocumentSchema):
    """
        Use this mixin in ADM Columns that return a numerical value
        or can be configured to return a numerical value.

        An example of such a column is the CaseCountADMColumn.

        How this property is used:
            ADMColumns with returns_numerical = True will show up as options for other columns
            that perform calculations based on the results of multiple columns.
            - example: CompareADMColumn
    """
    returns_numerical = BooleanProperty(default=True)


class IgnoreDatespanADMColumnMixin(DocumentSchema):
    """
        Use this mixin when you have an ADM Column that can return different results based on
        whether it keys on startdate -> enddate, or across the duration of the entire project.

        tldr:
        True -> do not filter view by the stardate and enddate
        False -> filter the view by the startdate and enddate
    """
    ignore_datespan = BooleanProperty(default=True)


class ADMDocumentBase(Document, InterfaceEditableItemMixin):
    """
        For all things ADM.
        The important thing is that default versions of ADM items (reports and columns) are unique for domain + slug
        pairings.
        ---
        slug
            - human-readable identifier
            - global defaults have no domain specified and are identified by their slug
            - domain-specific defaults / overrides have a domain specified and are identified by
                the domain, slug, and is_default=True
        domain
            - when no domain name is specified, the ADMColumn or ADMReport will be the default for all domains
                that access it.
            - this default can be overridden when you have an ADMColumn or an ADMReport with the same slug
                but the domain name is not empty. When a domain tries to access that ADMColumn or ADMReport,
                then it will default to that domain-specific column / report definition---otherwise it will default
                to the global default with no domain specified (if that exists).
        is_default
            - relevant when the domain is specified
            - all reports/columns with no domain specified have is_default=True always.
    """
    slug = StringProperty(default="")
    domain = StringProperty()
    is_default = BooleanProperty(default=True)

    name = StringProperty(default="")
    description = StringProperty(default="")
    date_modified = DateTimeProperty()

    @property
    def editable_item_button(self):
        return mark_safe("""<a href="#updateADMItemModal"
        class="btn"
        data-item_id="%s"
        onclick="adm_interface.update_item(this)"
        data-toggle="modal"><i class="icon icon-pencil"></i> Edit</a>""" % self.get_id)

    @property
    def editable_item_display_columns(self):
        return ["slug", "domain", "name", "description"]

    def _boolean_label(self, value, yes_text="Yes", no_text="No"):
        return mark_safe('<span class="label label-%s">%s</span>' %
                         ("success" if value else "warning", yes_text if value else no_text))

    def editable_item_update(self, overwrite=True, **kwargs):
        for key, item in kwargs.items():
            try:
                setattr(self, key, item)
            except AttributeError:
                pass
        self.date_modified = datetime.datetime.utcnow()
        self.save()

    def editable_item_format_displayed_property(self, key, property):
        if isinstance(property, bool):
            return self._boolean_label(property)
        if key == 'domain':
            return mark_safe('<span class="label label-inverse">%s</span>' % property)\
            if property else "Global Default"
        return super(ADMDocumentBase, self).editable_item_format_displayed_property(key, property)

    @classmethod
    def is_editable_item_valid(cls, existing_item=None, **kwargs):
        slug = kwargs.get('slug')
        domain = kwargs.get('domain')
        existing_doc = cls.get_default(slug, domain=domain, wrap=False)
        if existing_item:
            return existing_item.slug == slug or not existing_doc
        return not existing_doc

    @classmethod
    def editable_item_create(cls, overwrite=True, **kwargs):
        item = cls()
        item.editable_item_update(**kwargs)
        return item

    @classmethod
    def defaults_couch_view(cls):
        raise NotImplementedError

    @classmethod
    def get_correct_wrap(cls, docid):
        try:
            adm_doc = get_db().get(docid)
            adm_class = adm_doc.get('doc_type')
            adm = to_function('corehq.apps.adm.models.%s' % adm_class)
            return adm.wrap(adm_doc)
        except Exception:
            pass
        return None

    @classmethod
    def key_defaults(cls, slug, domain=None, **kwargs):
        keys = list()
        if domain:
            keys.append(["defaults domain slug", domain, slug])
        keys.append(["defaults global slug", slug])
        return keys

    @classmethod
    def get_default(cls, slug, domain=None, wrap=True, **kwargs):
        keys = cls.key_defaults(slug, domain, **kwargs)
        data = None
        for key in keys:
            data = get_db().view(cls.defaults_couch_view(),
                startkey=key,
                endkey=key+[{}],
                reduce=False
            ).first()
            if data:
                break
        if data and wrap:
            return cls.get_correct_wrap(data.get('id'))
        return data


class ADMColumn(ADMDocumentBase):
    """
        The basic ADM Column.
        ADM columns are unique by slug.
        ---
        Usages of ADMDocumentBase properties:
            name
                - text in the column's header in an ADM Report
            description
                - text that shows up when you hover over the info (i) icon next to the column's name
                    in the column's header
    """
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

    def editable_item_format_displayed_property(self, key, property):
        if key == "name":
            return "%s" % property
        return super(ADMColumn, self).editable_item_format_displayed_property(key, property)

    def set_report_values(self, **kwargs):
        """
            This is called when rendering ADM report. Insert any relevant filters here.
        """
        datespan = kwargs.get('datespan')
        self._report_datespan = datespan if isinstance(datespan, DateSpan) else None
        domain = kwargs.get('domain')
        self._report_domain = domain

    def raw_value(self, **kwargs):
        raise NotImplementedError

    def clean_value(self, value):
        return value

    def html_value(self, value):
        return value

    @classmethod
    def defaults_couch_view(cls):
        return 'adm/all_default_columns'

    @classmethod
    def column_type(cls):
        return cls.__name__


class CouchViewADMColumn(ADMColumn):
    """
        Use this for generic columns that pull data straight from specific couch views.
    """
    couch_view = StringProperty(default="")
    key_format = StringProperty(default="<domain>, <user_id>, <datespan>")

    def __init__(self, _d=None, **kwargs):
        super(CouchViewADMColumn, self).__init__(_d, **kwargs)
        self.key_kwargs = {u'{}': {}}
    
    @property
    def editable_item_display_columns(self):
        return super(CouchViewADMColumn, self).editable_item_display_columns + \
               ["couch_view", "key_format"]

    @property
    @memoized
    def couch_key(self):
        keys = self.key_format.split(",")
        key_vals = []
        for key in keys:
            key = key.strip()
            key_vals.append(self.key_kwargs.get(key, key))
        return key_vals

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

    def _format_keywords_in_kwargs(self, **kwargs):
        return dict([("<%s>" % k, v) for k, v in kwargs.items()])

    def set_report_values(self, **kwargs):
        super(CouchViewADMColumn, self).set_report_values(**kwargs)
        self.key_kwargs.update(self._format_keywords_in_kwargs(**kwargs))

    def editable_item_format_displayed_property(self, key, property):
        if key == 'key_format':
            return '[%s]' % escape(property)
        return super(CouchViewADMColumn, self).editable_item_format_displayed_property(key, property)

    def get_couch_view_data(self, key, datespan=None):
        data = self.view_results(**utils.standard_start_end_key(key, datespan))
        return data.all() if data else None

    def view_results(self, reduce=False, **kwargs):
        try:
            data = get_db().view(self.couch_view,
                reduce=reduce,
                **kwargs
            )
        except Exception:
            data = None
        return data

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


class ReducedADMColumn(CouchViewADMColumn, NumericalADMColumnMixin, IgnoreDatespanADMColumnMixin):
    """
        Returns the value of the reduced view of whatever couch_view is specified.
        Generally used to retrieve countable items.
    """
    @property
    def editable_item_display_columns(self):
        return super(ReducedADMColumn, self).editable_item_display_columns + ["returns_numerical", "ignore_datespan"]

    def aggregate(self, values):
        return reduce(lambda x, y: x+ y, values) if self.returns_numerical \
            else ', '.join(values)
    
    def editable_item_update(self, overwrite=True, **kwargs):
        self.ignore_datespan = kwargs.get('ignore_datespan', False)
        super(ReducedADMColumn, self).editable_item_update(overwrite, **kwargs)

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


class DaysSinceADMColumn(CouchViewADMColumn, NumericalADMColumnMixin):
    """
        The number of days since enddate <property_name>'s date.
        property_name should be a datetime.
    """
    property_name = StringProperty(default="")
    start_or_end = StringProperty(default="enddate")

    @property
    def editable_item_display_columns(self):
        return super(DaysSinceADMColumn, self).editable_item_display_columns + ["property_name", "start_or_end"]

    def _get_property_from_doc(self, doc, property):
        if isinstance(doc, dict) and len(property) > 0:
            return self._get_property_from_doc(doc.get(property[0]), property[1:-1])
        return doc

    def editable_item_format_displayed_property(self, key, property):
        if key == "start_or_end":
            from corehq.apps.adm.forms import DATESPAN_CHOICES
            choices = dict(DATESPAN_CHOICES)
            return "%s and %s" % (self.property_name, choices.get(property, "--"))
        return super(DaysSinceADMColumn, self).editable_item_format_displayed_property(key, property)

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
        Use this for columns that can have end-user configurable properties.
        ---
        is_configurable
            - if this is True, a this column will show up in a UI available to domain admins that will
                allow them to configure the default domain-specific version of this column
    """
    is_configurable = BooleanProperty(default=False)
    config_doc = "ConfigurableADMColumn"

    @property
    def editable_item_display_columns(self):
        return ["column_type"] + super(ConfigurableADMColumn, self).editable_item_display_columns + \
               ["is_configurable", "configurable_properties_in_row"]

    @property
    def editable_item_button(self):
        return mark_safe("""<a href="#updateADMItemModal"
        class="btn"
        data-item_id="%s"
        data-form_class="%s"
        onclick="adm_interface.update_item(this)"
        data-toggle="modal"><i class="icon icon-pencil"></i> Edit</a>""" %\
                         (self.get_id, "%sForm" % self.__class__.__name__))

    @property
    def configurable_properties(self):
        return []

    @property
    @memoized
    def configurable_properties_in_row(self):
        properties = ['<dl class="dl-horizontal" style="margin:0;padding:0;">']
        for key in self.configurable_properties:
            property = getattr(self, key)
            properties.append("<dt>%s</dt>" % self.format_key(key))
            properties.append("<dd>%s</dd>" % self.editable_item_format_displayed_property(key, property))
        properties.append("</dl>")
        return mark_safe("\n".join(properties))

    def editable_item_format_displayed_property(self, key, property):
        if isinstance(property, instancemethod):
            return property()
        return super(ConfigurableADMColumn, self).editable_item_format_displayed_property(key, property)

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
                logging.error("Encountered an error when trying to get configurable column with id %s: %s" %
                        (key[-1], e))
        return wrapped_data

    @classmethod
    def column_type(cls):
        return "Case Count"


class CompareADMColumn(ConfigurableADMColumn):
    """
        Grabs two ADMColumns that return numerical values.
        Computes the ratio, returns the percent and the ratio.
        ---
        numerator_ref
            - self.is_default: ADMColumn slug
            - else: ADMColumn ID

        denominator_ref
            - self.is_default: ADMColumn slug
            - else: ADMColumn ID
    """
    numerator_ref = StringProperty(default="")
    denominator_ref = StringProperty(default="")

    @property
    def configurable_properties(self):
        return ["numerator_ref", "denominator_ref"]

    @property
    @memoized
    def numerator(self):
        if self.is_default:
            return ADMColumn.get_default(self.numerator_ref, domain=self.report_domain)
        return ADMColumn.get_correct_wrap(self.numerator_ref)

    @property
    @memoized
    def denominator(self):
        if self.is_default:
            return ADMColumn.get_default(self.denominator_ref, domain=self.report_domain)
        return ADMColumn.get_correct_wrap(self.denominator_ref)

    def set_report_values(self, **kwargs):
        super(CompareADMColumn, self).set_report_values(**kwargs)
        if self.numerator:
            self.numerator.set_report_values(**kwargs)
        if self.denominator:
            self.denominator.set_report_values(**kwargs)

    def format_key(self, key):
        if key == "numerator_ref" or key == "denominator_ref":
            return key.replace("_ref", "").title()
        return super(CompareADMColumn, self).format_key(key)

    def editable_item_format_displayed_property(self, key, property):
        if key == "numerator_ref" or key == 'denominator_ref':
            try:
                col = getattr(self, key.replace('_ref', ''))
                configurable = '<span class="label label-success">Configurable</span><br />'
                return mark_safe('%s %s(%s)' % \
                       (col.name, configurable if col.is_configurable else '', property))
            except Exception:
                return "Ref Not Found (%s)" % property
        return super(CompareADMColumn, self).editable_item_format_displayed_property(key, property)

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
    def default_numerical_column_options(cls):
        key = ["numerical slug"]
        data = get_db().view("adm/all_default_columns",
            group=True,
            group_level=2,
            startkey=key,
            endkey=key+[{}]
        ).all()
        return [("", "Select a Column")] + [(item.get('key', [])[-1], item.get('key', [])[-1]) for item in data]

    @classmethod
    def column_type(cls):
        return "Comparison"


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
            return ", ".join(property) if property and property[0] else 'N/A'
        if key == 'case_status':
            case_status_options = dict(CASE_STATUS_OPTIONS)
            return case_status_options[property or '']
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
        if self.filter_option == CASE_FILTER_OPTIONS[2][0] and self.case_types:
            filtered_cases = list()
            for case in all_cases:
                if isinstance(case, CommCareCase):
                    case_type = case.type
                else:
                    try:
                        case_type = case.get('value', {}).get('type')
                    except Exception:
                        case_type = None
                if case_type not in self.case_types:
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


class CaseCountADMColumn(ConfigurableADMColumn, CaseFilterADMColumnMixin,
    NumericalADMColumnMixin, IgnoreDatespanADMColumnMixin):
    """
        Cases that are still open but date_modified is older than <inactivity_milestone> days from the
        enddate of the report.

    """
    inactivity_milestone = IntegerProperty(default=0)

    @property
    def configurable_properties(self):
        return ["case_status", "filter_option", "case_types", "inactivity_milestone", "ignore_datespan"]

    def editable_item_format_displayed_property(self, key, property):
        if key == 'inactivity_milestone':
            return "%s days" % property if property else "N/A"
        if key == 'ignore_datespan' and self.inactivity_milestone > 0:
            return 'N/A'
        case_filter_props = self.format_case_filter_properties(key, property)
        if case_filter_props is not None:
            return case_filter_props
        return super(CaseCountADMColumn, self).editable_item_format_displayed_property(key, property)

    def raw_value(self, **kwargs):
        user_id = kwargs.get('user_id')
        datespan_keys = None
        if self.inactivity_milestone > 0:
            # inactivity milestone takes precedence over any ignore_datespan configurations
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


class ADMReport(ADMDocumentBase):
    """
        An ADMReport describes how to display a group of ADMColumns and in what
        section or domain to display them.
        ---
        reporting_section
            - This specifies the slug for the reporting section in the side navigation of the ADM
                Reports page.
        column_refs
            - A list of either ADMColumn slugs or couch doc ids referring to what columns should be visible in
                the report view.
            - is_default = True -> refs are slugs
            - is_default = False -> refs are couch doc ids
        key_type
            - currently the data from ADMColumn references the user_id.
        ---
        Usages of parent properties:
            slug
                - ADM Report URLs look like /a/<domain>/reports/adm/<reporting_section>/<slug>
            name
                - The title of the ADMReport.
            description
                - A short description of the report. This currently only shows up as the title attribute
                    of the link to the report in the navigation pane of ADM Reports.
    """
    reporting_section = StringProperty(default="supervisor")
    column_refs = ListProperty()
    key_type = StringProperty(default="user_id")

    base_doc = "ADMReport"

    @property
    def editable_item_display_columns(self):
        """
            Not to be confused with ADM Columns (self.columns)
        """
        original = super(ADMReport, self).editable_item_display_columns
        return ["reporting_section"] + original + ["column_refs", "key_type"]

    @property
    @memoized
    def columns(self):
        cols = []
        for ref in self.column_refs:
            if self.is_default:
                column = ADMColumn.get_default(ref, domain=self.viewing_domain)
            else:
                column = ADMColumn.get_correct_wrap(ref)
            if column:
                cols.append(column)
        return cols

    _viewing_domain = None
    @property
    def viewing_domain(self):
        """
            The domain that is viewing this report.
            This will be different from self.domain if this is a global default report.
        """
        if self._viewing_domain is None:
            self._viewing_domain = self.domain
        return self._viewing_domain

    def set_domain_specific_values(self, domain):
        self._viewing_domain = domain

    def editable_item_format_displayed_property(self, key, property):
        if key == 'column_refs':
            ol = ['<ol>']
            for ref in property:
                if self.is_default:
                    col = ADMColumn.get_default(ref)
                else:
                    col = ADMColumn.get_correct_wrap(ref)
                ol.append('<li>%s <span class="label label-info">%s</span></li>' % (col.name, col.slug))
            ol.append('</ol>')
            return  mark_safe("\n".join(ol))
        if key == 'reporting_section':
            sections = dict(REPORT_SECTION_OPTIONS)
            return sections.get(property, "Unknown")
        return super(ADMReport, self).editable_item_format_displayed_property(key, property)

    @classmethod
    def defaults_couch_view(cls):
        return "adm/all_default_reports"

    @classmethod
    def get_active_slugs(cls, domain, section):
        all_slugs = list()

        key = ["defaults domain slug", domain, section]
        domain_defaults = get_db().view(cls.defaults_couch_view(),
            group=True,
            group_level=4,
            startkey=key,
            endkey=key+[{}]
        ).all()
        all_slugs.extend([item.get('key', [])[-1] for item in domain_defaults])

        key = ["defaults global slug", section]
        global_defaults = get_db().view(cls.defaults_couch_view(),
            group=True,
            group_level=3,
            startkey=key,
            endkey=key+[{}]
        ).all()
        all_slugs.extend([item.get('key', [])[-1] for item in global_defaults])

        return list(set(all_slugs))


    @classmethod
    def get_default_subreports(cls, domain, section, wrap=False):
        active_slugs = cls.get_active_slugs(domain, section)
        all_reports = list()
        for slug in active_slugs:
            default_report = ADMReport.get_default(slug, domain=domain, wrap=wrap, section=section)
            if default_report:
                all_reports.append(default_report)
        return all_reports

    @classmethod
    def key_defaults(cls, slug, domain=None, **kwargs):
        section = kwargs.get('section')
        keys = list()
        if domain:
            keys.append(["defaults domain slug", domain, section, slug])
        keys.append(["defaults global slug", section, slug])
        return keys