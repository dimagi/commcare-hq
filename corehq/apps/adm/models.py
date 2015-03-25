import logging
import pytz
import dateutil
from couchdbkit.ext.django.schema import *
from casexml.apps.case.models import CommCareCase
from corehq.apps.adm.admin.crud import *
from corehq.apps.crud.models import AdminCRUDDocumentMixin
from corehq.apps.groups.models import Group
from corehq.util.timezones.conversions import UserTime
from dimagi.utils.couch.database import get_db
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.modules import to_function
from corehq.util.timezones import utils as tz_utils
from corehq.apps.users.models import CommCareUser
from copy import copy

def standard_start_end_key(key, datespan=None):
    startkey_suffix = [datespan.startdate_param_utc] if datespan else []
    endkey_suffix = [datespan.enddate_param_utc] if datespan else [{}]
    return dict(
        startkey=key+startkey_suffix,
        endkey=key+endkey_suffix
    )

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
SORT_BY_DIRECTION_OPTIONS = [
    ('asc', "Ascending"),
    ('desc', "Descending"),
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


class BaseADMDocument(Document, AdminCRUDDocumentMixin):
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

    _admin_crud_class = ADMAdminCRUDManager

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


class BaseADMColumn(BaseADMDocument):
    """
        The basic ADM Column.
        ADM columns are unique by slug.
        ---
        Usages of BaseADMDocument properties:
            name
                - text in the column's header in an ADM Report
            description
                - text that shows up when you hover over the info (i) icon next to the column's name
                    in the column's header
    """
    base_doc = "ADMColumn"

    _admin_crud_class = ColumnAdminCRUDManager

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

    def _get_raw_vals_from_data(self, column_data):
        return [d.get('sort_key') for d in column_data if d.get('sort_key') is not None]

    def calculate_totals(self, column_data):
        raw_vals = self._get_raw_vals_from_data(column_data)
        return sum(raw_vals)

    def calculate_averages(self, column_data):
        raw_vals = self._get_raw_vals_from_data(column_data)
        return sum(raw_vals)/len(raw_vals) if raw_vals else 0

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


class CouchViewADMColumn(BaseADMColumn):
    """
        Use this for generic columns that pull data straight from specific couch views.
    """
    couch_view = StringProperty(default="")
    key_format = StringProperty(default="<domain>, <user_id>, <datespan>")

    _admin_crud_class = CouchViewColumnAdminCRUDManager

    def __init__(self, _d=None, **kwargs):
        super(CouchViewADMColumn, self).__init__(_d, **kwargs)
        # _key_kwargs must start with an underscore
        # or else jsonobject will interpret it as json, which it's not
        self._key_kwargs = {u'{}': {}}

    @property
    @memoized
    def couch_key(self):
        keys = self.key_format.split(",")
        key_vals = []
        for key in keys:
            key = key.strip()
            key_vals.append(self._key_kwargs.get(key, key))
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
        if user_id is None:
            return [key]
        def _repl(k, index, id):
            ret = copy(k)
            ret[index] = id
            return ret
        return [_repl(key, index, id) for id in CommCareUser.get(user_id).get_owner_ids()]

    def _format_keywords_in_kwargs(self, **kwargs):
        return dict([("<%s>" % k, v) for k, v in kwargs.items()])

    def set_report_values(self, **kwargs):
        super(CouchViewADMColumn, self).set_report_values(**kwargs)
        self._key_kwargs.update(self._format_keywords_in_kwargs(**kwargs))

    def get_couch_view_data(self, key, datespan=None):
        data = self.view_results(**standard_start_end_key(key, datespan))
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
            elif isinstance(key, basestring):
                cleaned_key.append(kwargs.get(key, key))
            else:
                cleaned_key.append(key)
        return self.get_couch_view_data(cleaned_key, datespan)


class ReducedADMColumn(CouchViewADMColumn, NumericalADMColumnMixin, IgnoreDatespanADMColumnMixin):
    """
        Returns the value of the reduced view of whatever couch_view is specified.
        Generally used to retrieve countable items.
    """
    _admin_crud_class = ReducedColumnAdminCRUDManager

    def aggregate(self, values):
        return reduce(lambda x, y: x + y, values) if self.returns_numerical \
            else ', '.join(values)

    def get_couch_view_data(self, key, datespan=None):
        if self.ignore_datespan:
            datespan = None
        # for now, if you're working with users assume you use all
        # their owner ids in your query
        keys = [key] if not self.is_user_column else self._expand_user_key(key)
        def _val(key, datespan): 
            start_end = standard_start_end_key(key, datespan)
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

    _admin_crud_class = DaysSinceColumnAdminCRUDManager

    def _get_property_from_doc(self, doc, property):
        """
            Hmmm...I think I did something similar to this wtih MVP Indicators.
            todo: check that.
        """
        if isinstance(doc, dict) and len(property) > 0:
            return self._get_property_from_doc(doc.get(property[0]), property[1:-1])
        return doc

    def calculate_totals(self, column_data):
        return "--"

    def get_couch_view_data(self, key, datespan=None):
        default_value = None
        try:
            now = UserTime(
                getattr(datespan, self.start_or_end or "enddate"),
                datespan.timezone
            ).server_time().done().replace(tzinfo=pytz.utc)
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


class ConfigurableADMColumn(BaseADMColumn):
    """
        Use this for columns that can have end-user configurable properties.
        ---
        is_configurable
            - if this is True, a this column will show up in a UI available to domain admins that will
                allow them to configure the default domain-specific version of this column
    """
    is_configurable = BooleanProperty(default=False)
    config_doc = "ConfigurableADMColumn"

    _admin_crud_class = ConfigurableColumnAdminCRUDManager

    @property
    def configurable_properties(self):
        return []

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


class UserDataADMColumn(ConfigurableADMColumn):
    user_data_key = StringProperty()

    _admin_crud_class = ConfigurableColumnAdminCRUDManager

    @property
    def configurable_properties(self):
        return ["user_data_key"]

    def raw_value(self, **kwargs):
        user_id = kwargs.get('user_id')
        try:
            user = CommCareUser.get(user_id)
            return user.user_data.get(self.user_data_key)
        except Exception:
            pass
        return None

    def clean_value(self, value):
        return "--" if value is None else value

    def html_value(self, value):
        return self.clean_value(value)

    def calculate_averages(self, column_data):
        return "--"

    def calculate_totals(self, column_data):
        return "--"

    @classmethod
    def column_type(cls):
        return "User Data"


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

    _admin_crud_class = CompareColumnAdminCRUDManager

    @property
    def configurable_properties(self):
        return ["numerator_ref", "denominator_ref"]

    @property
    def returns_numerical(self):
        return True

    @property
    @memoized
    def numerator(self):
        if self.is_default:
            return ConfigurableADMColumn.get_default(self.numerator_ref, domain=self.report_domain)
        return ConfigurableADMColumn.get_correct_wrap(self.numerator_ref)

    @property
    @memoized
    def denominator(self):
        if self.is_default:
            return ConfigurableADMColumn.get_default(self.denominator_ref, domain=self.report_domain)
        return ConfigurableADMColumn.get_correct_wrap(self.denominator_ref)

    def _get_fractions(self, column_data):
        formatted_vals = [d.get('html') for d in column_data if d.get('sort_key', -1) >= 0]
        numerators = []
        denominators = []
        for v in formatted_vals:
            fraction = v.split(' ')[0].split('/')
            numerators.append(int(fraction[0]))
            denominators.append(int(fraction[1]))
        return numerators, denominators

    def calculate_totals(self, column_data):
        numerators, denominators = self._get_fractions(column_data)
        n_sum = sum(numerators) if numerators else 0
        d_sum = sum(denominators) if denominators else 0
        return self.html_value(dict(
            numerator=n_sum,
            denominator=d_sum,
        ))

    def calculate_averages(self, column_data):
        numerators, denominators = self._get_fractions(column_data)
        n_avg = sum(numerators)/len(numerators) if numerators else 0
        d_avg = sum(denominators)/len(denominators) if denominators else 0
        return self.html_value(dict(
            numerator=n_avg,
            denominator=d_avg,
        ))

    def set_report_values(self, **kwargs):
        super(CompareADMColumn, self).set_report_values(**kwargs)
        if self.numerator:
            self.numerator.set_report_values(**kwargs)
        if self.denominator:
            self.denominator.set_report_values(**kwargs)

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
            return float(n)/float(d)*100
        except Exception:
            return -1

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
        Returns the count of the number of cases specified by the filters in CaseFilterADMColumnMixin and
        inactivity_milestone.
    """
    inactivity_milestone = IntegerProperty(default=0)

    _admin_crud_class = CaseCountColumnCRUDManager

    @property
    def configurable_properties(self):
        return ["case_status", "filter_option", "case_types", "inactivity_milestone", "ignore_datespan"]

    def raw_value(self, **kwargs):
        user_id = kwargs.get('user_id')
        datespan_keys = None
        if self.inactivity_milestone > 0:
            # inactivity milestone takes precedence over any ignore_datespan configurations
            milestone_days_ago = UserTime(
                self.report_datespan.enddate, self.report_datespan.timezone
            ).server_time().done() - datetime.timedelta(days=self.inactivity_milestone)
            # in refactoring tz stuff,
            # milestone_days_ago is now tz naive, so isoformat()
            # no longer has +00:00 at the end. I think that's fine.
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

    @classmethod
    def column_type(cls):
        return "Case Count"


class ADMReport(BaseADMDocument):
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
    sort_by_default = StringProperty()
    sort_by_direction = StringProperty(
        choices=[d[0] for d in SORT_BY_DIRECTION_OPTIONS],
        default=SORT_BY_DIRECTION_OPTIONS[0][0]
    )
    key_type = StringProperty(default="user_id")

    base_doc = "ADMReport"

    _admin_crud_class = ADMReportCRUDManager

    @property
    @memoized
    def columns(self):
        cols = []
        for ref in self.column_refs:
            if self.is_default:
                column = BaseADMColumn.get_default(ref, domain=self.viewing_domain)
            else:
                column = BaseADMColumn.get_correct_wrap(ref)
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

    @property
    def default_sort_params(self):
        sort_ind = 0
        for ind, col in enumerate(self.columns):
            if self.sort_by_default == col.slug:
                sort_ind = 1+ind
                break
        return [[sort_ind, self.sort_by_direction]]

    def set_domain_specific_values(self, domain):
        self._viewing_domain = domain

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
