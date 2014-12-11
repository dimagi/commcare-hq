from couchdbkit import ResourceNotFound
from couchdbkit.ext.django.schema import Document, StringListProperty
from couchdbkit.ext.django.schema import StringProperty, DictProperty, ListProperty
from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.factory import FilterFactory, IndicatorFactory
from corehq.apps.userreports.indicators import CompoundIndicator, ConfigurableIndicatorMixIn
from corehq.apps.userreports.reports.factory import ReportFactory, ChartFactory, ReportFilterFactory
from corehq.apps.userreports.reports.specs import FilterSpec
from django.utils.translation import ugettext as _
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.mixins import UnicodeMixIn


DELETED_DOC_TYPES = {
    'CommCareCase': [
        'CommCareCase-Deleted',
    ],
    'XFormInstance': [
        'XFormInstance-Deleted',
        'XFormArchived',
        'XFormDeprecated',
    ],
}


class DataSourceConfiguration(UnicodeMixIn, ConfigurableIndicatorMixIn, CachedCouchDocumentMixin, Document):
    """
    A data source configuration. These map 1:1 with database tables that get created.
    Each data source can back an arbitrary number of reports.
    """
    domain = StringProperty(required=True)
    referenced_doc_type = StringProperty(required=True)
    table_id = StringProperty(required=True)
    display_name = StringProperty()
    configured_filter = DictProperty()
    configured_indicators = ListProperty()
    named_filters = DictProperty()

    def __unicode__(self):
        return u'{} - {}'.format(self.domain, self.display_name)

    @property
    def filter(self):
        return self._get_filter([self.referenced_doc_type])

    @property
    def deleted_filter(self):
        return self._get_filter(DELETED_DOC_TYPES[self.referenced_doc_type])

    def _get_filter(self, doc_types):
        extras = (
            [self.configured_filter]
            if self.configured_filter else []
        )
        built_in_filters = [
            {
                'type': 'property_match',
                'property_name': 'domain',
                'property_value': self.domain,
            },
            {
                'type': 'or',
                'filters': [
                    {
                        'type': 'property_match',
                        'property_name': 'doc_type',
                        'property_value': doc_type,
                    }
                    for doc_type in doc_types
                ],
            },
        ]
        return FilterFactory.from_spec(
            {
                'type': 'and',
                'filters': built_in_filters + extras,
            },
            context=self.named_filter_objects,
        )

    @property
    @memoized
    def named_filter_objects(self):
        return {name: FilterFactory.from_spec(filter, {})
                for name, filter in self.named_filters.items()}

    @property
    def indicators(self):
        doc_id_indicator = IndicatorFactory.from_spec({
            "column_id": "doc_id",
            "type": "raw",
            "display_name": "document id",
            "datatype": "string",
            "property_name": "_id",
            "is_nullable": False,
            "is_primary_key": True,
        }, self.named_filter_objects)
        return CompoundIndicator(
            self.display_name,
            [doc_id_indicator] + [
                IndicatorFactory.from_spec(indicator, self.named_filter_objects)
                for indicator in self.configured_indicators
            ]
        )

    def get_columns(self):
        return self.indicators.get_columns()

    def get_values(self, item):
        if self.filter.filter(item):
            return self.indicators.get_values(item)
        else:
            return []

    def validate(self, required=True):
        super(DataSourceConfiguration, self).validate(required)
        # these two properties implicitly call other validation
        self.filter
        self.indicators

    @classmethod
    def by_domain(cls, domain):
        return sorted(
            cls.view('userreports/data_sources_by_domain', key=domain, reduce=False, include_docs=True),
            key=lambda config: config.display_name
        )

    @classmethod
    def all(cls):
        ids = [res['id'] for res in cls.view('userreports/data_sources_by_domain',
                                             reduce=False, include_docs=False)]
        for result in iter_docs(cls.get_db(), ids):
            yield cls.wrap(result)


class ReportConfiguration(UnicodeMixIn, CachedCouchDocumentMixin, Document):
    """
    A report configuration. These map 1:1 with reports that show up in the UI.
    """
    domain = StringProperty(required=True)
    config_id = StringProperty(required=True)
    title = StringProperty()
    description = StringProperty()
    aggregation_columns = StringListProperty()
    filters = ListProperty()
    columns = ListProperty()
    configured_charts = ListProperty()

    def __unicode__(self):
        return u'{} - {}'.format(self.domain, self.title)

    @property
    @memoized
    def config(self):
        try:
            return DataSourceConfiguration.get(self.config_id)
        except ResourceNotFound:
            raise BadSpecError(_('The data source referenced by this report could not be found.'))

    @property
    @memoized
    def ui_filters(self):
        return [ReportFilterFactory.from_spec(f) for f in self.filters]

    @property
    @memoized
    def charts(self):
        return [ChartFactory.from_spec(g._obj) for g in self.configured_charts]

    @property
    def table_id(self):
        return self.config.table_id

    def get_ui_filter(self, filter_slug):
        for filter in self.ui_filters:
            if filter.name == filter_slug:
                return filter
        return None

    def validate(self, required=True):
        def _check_for_duplicate_slugs(filters):
            slugs = [FilterSpec.wrap(f).slug for f in filters]
            # http://stackoverflow.com/questions/9835762/find-and-list-duplicates-in-python-list
            duplicated_slugs = set(
                [slug for slug in slugs if slugs.count(slug) > 1]
            )
            if len(duplicated_slugs) > 0:
                raise BadSpecError(
                    _('Filters cannot contain duplicate slugs: %s')
                    % ', '.join(sorted(duplicated_slugs))
                )

        super(ReportConfiguration, self).validate(required)

        # these calls implicitly do validation
        ReportFactory.from_spec(self)
        self.ui_filters
        self.charts

        _check_for_duplicate_slugs(self.filters)

    @classmethod
    def by_domain(cls, domain):
        return sorted(
            cls.view('userreports/report_configs_by_domain', key=domain, reduce=False, include_docs=True),
            key=lambda report: report.title,
        )

    @classmethod
    def all(cls):
        ids = [res['id'] for res in cls.view('userreports/report_configs_by_domain',
                                             reduce=False, include_docs=False)]
        for result in iter_docs(cls.get_db(), ids):
            yield cls.wrap(result)
