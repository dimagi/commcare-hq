from datetime import datetime, date, time
from dimagi.utils.dates import DateSpan

CONFIG_TYPE_BOOLEAN = 'boolean'
CONFIG_TYPE_STRING = 'string'
CONFIG_TYPE_INTEGER = 'integer'
CONFIG_TYPE_DATE = 'date'

CONFIG_DATA_TYPES = [CONFIG_TYPE_BOOLEAN, CONFIG_TYPE_STRING,
                     CONFIG_TYPE_INTEGER, CONFIG_TYPE_DATE]

DATE_FORMAT = "%Y-%m-%d"


class BaseMetaModel(object):
    """
    Assumes class will be instantiated with ``fields`` as 'args' and
    ``optional_fields`` as 'kwargs'.

    Ordering of args must match ordering in ``fields`` attribute.
    """
    fields = []
    optional_fields = []

    def __init__(self, *args, **kwargs):
        if not len(args) == len(self.fields):
            raise Exception("Unexpected fields. Expected '%s', got '%s'" % (self.fields, args))

        for field, value in dict(zip(self.fields, args)).items():
            setattr(self, field, value)

        for field in self.optional_fields:
            value = kwargs.pop(field, None)
            setattr(self, field, value)

        if kwargs:
            raise Exception("Unexpected kwargs %s" % kwargs)

        self.validate()

    def validate(self):
        pass

    def to_json(self):
        d = dict()
        for f in self.fields:
            d[f] = getattr(self, f)

        for f in self.optional_fields:
            val = getattr(self, f, None)
            if val is not None:
                d[f] = val

        return d


class ConfigItemMeta(BaseMetaModel):
    fields = ['slug', 'name', 'data_type']
    optional_fields = ['required', 'group_by', 'options', 'default', 'help_text']

    def validate(self):
        if self.data_type not in CONFIG_DATA_TYPES:
            raise ValueError('Unexpected value for data_type: %s' % self.data_type)


class IndicatorMeta(BaseMetaModel):
    fields = ['slug', 'name']
    optional_fields = ['group', 'help_text']


class IndicatorGroupMeta(BaseMetaModel):
    fields = ['slug', 'name']
    optional_fields = ['help_text']


class ReportApiSource(object):
    _meta_fields = ['config', 'indicators', 'indicator_groups']
    slug = ''
    name = ''

    def __init__(self, domain=None, request=None, config=None, meta_only=False):
        """
        One of request or config must be supplied.

        :param domain: The domain requesting data.
        :param request: The Django request object.
        :param config: Dict containing the configuration. See ``self.config_meta``.
        :param meta_only: If True just return the meta-data.
        """
        self.domain = domain
        self.config = config or dict()
        self.request = request
        self.meta_only = meta_only

        self.post_init()

    def post_init(self):
        if self.request:
            self._build_config_from_request()
        else:
            for item in self.config_meta:
                if item.slug not in self.config and item.default:
                    self.config[item.slug] = item.default

        self._convert_types()
        self._build_datespan()

    @property
    def config_meta(self):
        """
        Return a list of ConfigItemMeta instances or dict with appropriate keys.
        """
        raise NotImplementedError()

    @property
    def indicators_meta(self):
        """
        Return a list of IndicatorMeta instances.
        """
        raise NotImplementedError()

    @property
    def indicator_groups_meta(self):
        """
        Return a list of IndicatorGroupMeta instances.
        """
        pass

    @property
    def config_complete(self):
        """
        Return True if ``self.meta_only`` is False AND all required config params are satisfied.
        """
        missing_params = self.get_missing_params()
        print missing_params
        return not self.meta_only and not missing_params

    def get_missing_params(self):
        """
        Return a list of config params that are not satisfied.
        """
        if self.config is None:
            return [item.slug for item in self.config_meta if item.required]

        return [item.slug for item in self.config_meta if item.required and not self.config.get(item.slug)]

    def get_results(self):
        if self.config_complete:
            return self.results()
        else:
            return None

    def results(self):
        """
        Return a list of dicts mapping indicator slugs to values.

        e.g.
        [{
            'user': 'a',
            'indicator1': 10,
            'indicator2': 4
        },
        {
            'user': 'b,
            'indicator1': 8,
            'indicator2': 5
        }]

        """
        pass

    def api_meta(self, full=False):
        meta = dict(slug=self.slug, name=self.name)

        if full:
            for field in self._meta_fields:
                value = getattr(self, '%s_meta' % field) or []
                meta[field] = [item.to_json() if isinstance(item, BaseMetaModel) else item for item in value]

        return meta

    def _build_config_from_request(self):
        conf = dict([(item.slug, self.request.GET.get(item.slug, item.default)) for item in self.config_meta])
        indicators_param = self.request.GET.get('indicators')
        indicators = indicators_param.split(',') if indicators_param else None
        conf['indicator_slugs'] = indicators
        conf['domain'] = self.domain

        self.config = dict(conf)

    def _build_datespan(self):
        def date_or_nothing(param):
            if param in self.config and self.config[param]:
                val = self.config[param]
                if isinstance(val, date):
                    return datetime.combine(val, time())
                elif isinstance(val, datetime):
                    return val
                else:
                    return datetime.strptime(val, DATE_FORMAT)

        startdate = date_or_nothing('startdate')
        enddate = date_or_nothing('enddate')

        if startdate or enddate:
            self.config['datespan'] = DateSpan(startdate, enddate, DATE_FORMAT)

    def _convert_types(self):
        for item in self.config_meta:
            self.config[item.slug] = self._convert_type(item.data_type, self.config.get(item.slug, None))

    def _convert_type(self, data_type, param):
        if param is None or not isinstance(param, basestring):
            return param
        else:
            if data_type == CONFIG_TYPE_DATE:
                return datetime.strptime(param, DATE_FORMAT)
            elif data_type == CONFIG_TYPE_BOOLEAN:
                return param in ('True', 'true', 1)
            elif data_type == CONFIG_TYPE_INTEGER:
                return int(param)
            return param


def get_report_results(klass, domain, config, indicator_slugs=None, include_meta=False, meta_full=False):
    config['indicator_slugs'] = indicator_slugs
    report = klass(domain=domain, config=config)
    if not report.config_complete:
        raise ValueError('Report config incomplete. Missing config params: %s' % report.get_missing_params())

    data = report.get_results()

    ret = dict(results=data)
    if include_meta:
        ret.update(report.api_meta(full=meta_full))

    return ret
