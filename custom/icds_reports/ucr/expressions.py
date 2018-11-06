from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime

from jsonobject.base_properties import DefaultProperty
from quickcache.django_quickcache import get_django_quickcache
from six.moves import filter

from casexml.apps.case.xform import extract_case_blocks
from corehq.apps.receiverwrapper.util import get_version_from_appversion_text
from corehq.apps.userreports.const import XFORM_CACHE_KEY_PREFIX
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.mixins import NoPropertyTypeCoercionMixIn
from corehq.apps.userreports.specs import TypeProperty
from corehq.apps.userreports.util import add_tabbed_text
from corehq.apps.users.models import CommCareUser
from corehq.elastic import mget_query
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.toggles import ICDS_UCR_ELASTICSEARCH_DOC_LOADING, NAMESPACE_OTHER
from dimagi.ext.jsonobject import JsonObject, ListProperty, StringProperty, DictProperty, BooleanProperty


CUSTOM_UCR_EXPRESSIONS = [
    ('icds_parent_id', 'custom.icds_reports.ucr.expressions.parent_id'),
    ('icds_parent_parent_id', 'custom.icds_reports.ucr.expressions.parent_parent_id'),
    ('icds_get_case_forms_by_date', 'custom.icds_reports.ucr.expressions.get_case_forms_by_date'),
    ('icds_get_all_forms_repeats', 'custom.icds_reports.ucr.expressions.get_all_forms_repeats'),
    ('icds_get_last_form_repeat', 'custom.icds_reports.ucr.expressions.get_last_form_repeat'),
    ('icds_get_case_history', 'custom.icds_reports.ucr.expressions.get_case_history'),
    ('icds_get_case_history_by_date', 'custom.icds_reports.ucr.expressions.get_case_history_by_date'),
    ('icds_get_last_case_property_update', 'custom.icds_reports.ucr.expressions.get_last_case_property_update'),
    ('icds_get_case_forms_in_date', 'custom.icds_reports.ucr.expressions.get_forms_in_date_expression'),
    ('icds_get_app_version', 'custom.icds_reports.ucr.expressions.get_app_version'),
    ('icds_datetime_now', 'custom.icds_reports.ucr.expressions.datetime_now'),
    ('icds_boolean', 'custom.icds_reports.ucr.expressions.boolean_question'),
    ('icds_user_location', 'custom.icds_reports.ucr.expressions.icds_user_location'),
    ('icds_awc_owner_id', 'custom.icds_reports.ucr.expressions.awc_owner_id'),
]


class GetCaseFormsByDateSpec(JsonObject):
    type = TypeProperty('icds_get_case_forms_by_date')
    case_id_expression = DefaultProperty(required=False)
    xmlns = ListProperty(required=False)
    start_date = DefaultProperty(required=False)
    end_date = DefaultProperty(required=False)
    form_filter = DefaultProperty(required=False)


class GetAllFormsRepeatsSpec(JsonObject):
    type = TypeProperty('icds_get_all_forms_repeats')
    forms_expression = DefaultProperty(required=True)
    repeat_path = ListProperty(required=True)
    case_id_path = ListProperty(required=True)
    repeat_filter = DefaultProperty(required=False)
    case_id_expression = DefaultProperty(required=False)


class GetLastFormRepeatSpec(JsonObject):
    type = TypeProperty('icds_get_last_form_repeat')
    forms_expression = DefaultProperty(required=True)
    repeat_path = ListProperty(required=True)
    case_id_path = ListProperty(required=True)
    repeat_filter = DefaultProperty(required=False)
    case_id_expression = DefaultProperty(required=False)


class GetCaseHistorySpec(JsonObject):
    type = TypeProperty('icds_get_case_history')
    case_id_expression = DefaultProperty(required=True)
    start_date = DefaultProperty(required=False)
    end_date = DefaultProperty(required=False)
    xmlns = ListProperty(required=False)

    def configure(self, case_id_expression, case_forms_expression):
        self._case_id_expression = case_id_expression
        self._case_forms_expression = case_forms_expression

    def __call__(self, item, context=None):
        case_id = self._case_id_expression(item, context)
        if not case_id:
            return []

        forms = self._case_forms_expression(item, context)
        case_history = self._get_case_history(case_id, forms, context)
        return case_history

    def _get_case_history(self, case_id, forms, context):
        form_ids = tuple(f['_id'] for f in forms)
        cache_key = (self.__class__.__name__, case_id, form_ids)
        if context.get_cache_value(cache_key) is not None:
            return context.get_cache_value(cache_key)

        # TODO(Emord) looks like this is only used when getting the last
        # property update. maybe this could be optimized sort by received_on
        # and stop looking at forms once it finds the update
        case_history = []
        for f in forms:
            case_blocks = extract_case_blocks(f)
            if case_blocks:
                for case_block in case_blocks:
                    if case_block['@case_id'] == case_id:
                        case_history.append(case_block)

        context.set_cache_value(cache_key, case_history)
        return case_history

    def __str__(self):
        return "case_history(\n{cases}\n)".format(cases=add_tabbed_text(str(self._case_forms_expression)))


class GetCaseHistoryByDateSpec(JsonObject):
    type = TypeProperty('icds_get_case_history_by_date')
    case_id_expression = DefaultProperty(required=False)
    start_date = DefaultProperty(required=False)
    end_date = DefaultProperty(required=False)
    filter = DefaultProperty(required=False)
    xmlns = ListProperty(required=False)


class GetLastCasePropertyUpdateSpec(JsonObject):
    type = TypeProperty('icds_get_last_case_property_update')
    case_property = StringProperty(required=True)
    case_id_expression = DefaultProperty(required=False)
    start_date = DefaultProperty(required=False)
    end_date = DefaultProperty(required=False)
    filter = DefaultProperty(required=False)
    xmlns = ListProperty(required=False)


class FormsInDateExpressionSpec(NoPropertyTypeCoercionMixIn, JsonObject):
    type = TypeProperty('icds_get_case_forms_in_date')
    case_id_expression = DefaultProperty(required=True)
    xmlns = ListProperty(required=False)
    from_date_expression = DictProperty(required=False)
    to_date_expression = DictProperty(required=False)
    count = BooleanProperty(default=False)

    def configure(self, case_id_expression, from_date_expression=None, to_date_expression=None):
        self._case_id_expression = case_id_expression
        self._from_date_expression = from_date_expression
        self._to_date_expression = to_date_expression

    def __call__(self, item, context=None):
        case_id = self._case_id_expression(item, context)
        if self._from_date_expression:
            from_date = self._from_date_expression(item, context)
        else:
            from_date = None
        if self._to_date_expression:
            to_date = self._to_date_expression(item, context)
        else:
            to_date = None

        if not case_id:
            return []

        assert context.root_doc['domain']
        return self._get_forms(case_id, from_date, to_date, context)

    def _get_forms(self, case_id, from_date, to_date, context):
        domain = context.root_doc['domain']
        xmlns_tuple = tuple(self.xmlns)
        cache_key = (self.__class__.__name__, case_id, self.count, from_date,
                     to_date, xmlns_tuple)

        if context.get_cache_value(cache_key) is not None:
            return context.get_cache_value(cache_key)

        xform_ids = FormsInDateExpressionSpec._get_case_form_ids(case_id, context)
        # TODO(Emord) this will eventually break down when cases have a lot of
        # forms associated with them. perhaps change to intersecting two sets
        xforms = FormsInDateExpressionSpec._get_filtered_forms_from_es(case_id, xform_ids, context)
        if self.xmlns:
            xforms = [x for x in xforms if x['xmlns'] in xmlns_tuple]
        if from_date:
            xforms = [x for x in xforms if x['timeEnd'] >= from_date]
        if to_date:
            xforms = [x for x in xforms if x['timeEnd'] <= to_date]
        if self.count:
            count = len(xforms)
            context.set_cache_value(cache_key, count)
            return count

        if not ICDS_UCR_ELASTICSEARCH_DOC_LOADING.enabled(case_id, NAMESPACE_OTHER):
            form_ids = [x['_id'] for x in xforms]
            xforms = FormAccessors(domain).get_forms(form_ids)
            xforms = FormsInDateExpressionSpec._get_form_json_list(case_id, xforms, context, domain)

        context.set_cache_value(cache_key, xforms)
        return xforms

    @staticmethod
    def _get_filtered_forms_from_es(case_id, xform_ids, context):
        es_toggle_enabled = ICDS_UCR_ELASTICSEARCH_DOC_LOADING.enabled(case_id, NAMESPACE_OTHER)
        cache_key = (FormsInDateExpressionSpec.__name__, 'es_helper', case_id, tuple(xform_ids),
                     es_toggle_enabled)
        if context.get_cache_value(cache_key) is not None:
            return context.get_cache_value(cache_key)

        source = True if es_toggle_enabled else ['form.meta.timeEnd', 'xmlns', '_id']
        forms = FormsInDateExpressionSpec._bulk_get_forms_from_elasticsearch(xform_ids, source)
        context.set_cache_value(cache_key, forms)
        return forms

    @staticmethod
    def _get_case_form_ids(case_id, context):
        cache_key = (FormsInDateExpressionSpec.__name__, 'helper', case_id)
        if context.get_cache_value(cache_key) is not None:
            return context.get_cache_value(cache_key)

        domain = context.root_doc['domain']
        xform_ids = CaseAccessors(domain).get_case_xform_ids(case_id)
        context.set_cache_value(cache_key, xform_ids)
        return xform_ids

    @staticmethod
    def _get_form_json_list(case_id, xforms, context, domain):
        domain_filtered_forms = [f for f in xforms if f.domain == domain]
        return [FormsInDateExpressionSpec._get_form_json(f, context) for f in domain_filtered_forms]

    @staticmethod
    def _get_form_json(form, context):
        cached_form = FormsInDateExpressionSpec._get_cached_form_json(form, context)
        if cached_form is not None:
            return cached_form

        form_json = form.to_json()
        FormsInDateExpressionSpec._set_cached_form_json(form, form_json, context)
        return form_json

    @staticmethod
    def _bulk_get_form_json_from_es(forms):
        form_ids = [form.form_id for form in forms]
        es_forms = FormsInDateExpressionSpec._bulk_get_forms_from_elasticsearch(form_ids, source=True)
        return {
            f['_id']: f for f in es_forms
        }

    @staticmethod
    def _get_cached_form_json(form, context):
        return context.get_cache_value(FormsInDateExpressionSpec._get_form_json_cache_key(form))

    @staticmethod
    def _set_cached_form_json(form, form_json, context):
        context.set_cache_value(FormsInDateExpressionSpec._get_form_json_cache_key(form), form_json)

    @staticmethod
    def _get_form_json_cache_key(form):
        return (XFORM_CACHE_KEY_PREFIX, form.form_id)

    @staticmethod
    def _bulk_get_forms_from_elasticsearch(form_ids, source):
        forms = mget_query('forms', form_ids, source)
        return list(filter(None, [
            FormsInDateExpressionSpec._transform_time_end_and_filter_bad_data(f) for f in forms
        ]))

    @staticmethod
    def _transform_time_end_and_filter_bad_data(xform):
        xform = xform.get('_source', {})
        if not xform.get('xmlns', None):
            return None
        try:
            time = xform['form']['meta']['timeEnd']
        except KeyError:
            return None

        xform['timeEnd'] = datetime.strptime(time, '%Y-%m-%dT%H:%M:%S.%fZ').date()
        return xform

    def __str__(self):
        value = "case_forms[{case_id}]".format(case_id=self._case_id_expression)
        if self.from_date_expression or self.to_date_expression:
            value = "{value}[date={start} to {end}]".format(value=value,
                                                            start=self._from_date_expression,
                                                            end=self._to_date_expression)
        if self.xmlns:
            value = "{value}[xmlns=\n{xmlns}\n]".format(value=value,
                                                    xmlns=add_tabbed_text("\n".join(self.xmlns)))
        if self.count:
            value = "count({value})".format(value=value)
        return value


class GetAppVersion(JsonObject):
    type = TypeProperty('icds_get_app_version')
    app_version_string = DefaultProperty(required=True)

    def configure(self, app_version_string):
        self._app_version_string = app_version_string

    def __call__(self, item, context=None):
        app_version_string = self._app_version_string(item, context)
        return get_version_from_appversion_text(app_version_string)

    def __str__(self):
        return "Application Version"


class DateTimeNow(JsonObject):
    type = TypeProperty('icds_datetime_now')

    def __call__(self, item, context=None):
        return _datetime_now()

    def __str__(self):
        return "datetime.now"


class BooleanChoiceQuestion(JsonObject):
    type = TypeProperty('icds_boolean')
    boolean_property = DefaultProperty(required=True)
    true_values = ListProperty(required=True)
    false_values = ListProperty(required=True)
    nullable = BooleanProperty(default=True)


icds_ucr_quickcache = get_django_quickcache(memoize_timeout=60, timeout=60 * 60)


@icds_ucr_quickcache(('user_id',))
def _get_user_location_id(user_id):
    user = CommCareUser.get_db().get(user_id)
    return user.get('user_data', {}).get('commcare_location_id')


class ICDSUserLocation(JsonObject):
    """Heavily cached expression to reduce queries to Couch
    """
    type = TypeProperty('icds_user_location')
    user_id_expression = DefaultProperty(required=True)

    def configure(self, user_id_expression):
        self._user_id_expression = user_id_expression

    def __call__(self, item, context=None):
        user_id = self._user_id_expression(item, context)

        if not user_id:
            return None

        return _get_user_location_id(user_id)

    def __str__(self):
        return "User's location id"


class AWCOwnerId(JsonObject):
    type = TypeProperty('icds_awc_owner_id')
    case_id_expression = DefaultProperty(required=True)

    def configure(self, case_id_expression):
        self._case_id_expression = case_id_expression

    def __call__(self, item, context=None):
        case_id = self._case_id_expression(item, context)

        if not case_id:
            return None

        if item['owner_id'] and item['owner_id'] != '-':
            return item['owner_id']

        if item['owner_id'] == '-':
            accessor = CaseAccessors(context.root_doc['domain'])
            indices = {case_id}
            last_indices = set()
            while indices != last_indices:
                # assuming no loops
                last_indices |= indices
                indices |= set(accessor.get_indexed_case_ids(indices))

            cases = accessor.get_cases(list(indices))
            cases_with_owners = [
                case for case in cases
                if case.owner_id and case.owner_id != '-'
            ]
            if len(cases_with_owners) != 0:
                # This shouldn't happen in this world, but will feasibly
                # occur depending on our migration path from parent/child ->
                # extension cases. Once a migration path is decided revisit
                # alerting in this case
                return cases_with_owners[0].owner_id

            household_cases = [
                case for case in cases
                if case.type == 'household'
            ]
            assert len(household_cases) == 1
            household_case = household_cases[0]
            subcases = household_case.get_subcases(index_identifier='awc')
            cases_with_owners = [
                case for case in subcases
                if case.owner_id and case.owner_id != '-'
            ]
            assert len(cases_with_owners) == 1
            assert cases_with_owners[0].type == 'assignment'

            return cases_with_owners[0].owner_id

        return None

    def __str__(self):
        return "owner_id"


def _datetime_now():
    return datetime.utcnow()


def parent_id(spec, context):
    spec = {
        'type': 'nested',
        'argument_expression': {
            'type': 'indexed_case',
            'case_expression': {
                'type': 'root_doc',
                'expression': {
                    'type': 'identity'
                }
            },
            'index': 'parent'
        },
        'value_expression': {
            'type': 'property_name',
            'property_name': '_id'
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def parent_parent_id(spec, context):
    spec = {
        'type': 'nested',
        'argument_expression': {
            'type': 'indexed_case',
            'case_expression': {
                'type': 'indexed_case',
                'case_expression': {
                    'type': 'root_doc',
                    'expression': {
                        'type': 'identity'
                    }
                },
                'index': 'parent'
            },
            'index': 'parent'
        },
        'value_expression': {
            'type': 'property_name',
            'property_name': '_id'
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def get_case_forms_by_date(spec, context):
    GetCaseFormsByDateSpec.wrap(spec)
    if spec['case_id_expression'] is None:
        case_id_expression = {
            "type": "root_doc",
            "expression": {
                "type": "property_name",
                "property_name": "_id"
            }
        }
    else:
        case_id_expression = spec['case_id_expression']

    items_expression = {
        "type": "icds_get_case_forms_in_date",
        "case_id_expression": case_id_expression
    }
    if spec['start_date'] is not None:
        items_expression['from_date_expression'] = spec['start_date']
    if spec['end_date'] is not None:
        items_expression['to_date_expression'] = spec['end_date']
    if spec['xmlns']:
        items_expression['xmlns'] = spec['xmlns']
    if spec['form_filter'] is not None:
        items_expression = {
            "type": "filter_items",
            "filter_expression": spec['form_filter'],
            "items_expression": items_expression
        }

    spec = {
        "type": "sort_items",
        "sort_expression": {
            "type": "property_path",
            "property_path": [
                "form",
                "meta",
                "timeEnd"
            ],
            "datatype": "date"
        },
        "items_expression": items_expression
    }
    return ExpressionFactory.from_spec(spec, context)


def get_all_forms_repeats(spec, context):
    GetAllFormsRepeatsSpec.wrap(spec)

    if spec['case_id_expression'] is None:
        case_id_expression = {
            "type": "root_doc",
            "expression": {
                "type": "property_name",
                "property_name": "_id"
            }
        }
    else:
        case_id_expression = spec['case_id_expression']

    repeat_filters = []
    repeat_filters.append(
        {
            'type': 'boolean_expression',
            'operator': 'eq',
            'expression': {
                'type': 'property_path',
                'property_path': spec['case_id_path']
            },
            'property_value': case_id_expression
        }
    )

    if spec['repeat_filter'] is not None:
        repeat_filters.append(spec['repeat_filter'])

    spec = {
        'type': 'filter_items',
        'filter_expression': {
            'type': 'and',
            'filters': repeat_filters
        },
        'items_expression': {
            'type': 'flatten',
            'items_expression': {
                'type': 'map_items',
                'map_expression': {
                    'type': 'property_path',
                    'datatype': 'array',
                    'property_path': spec['repeat_path']
                },
                'items_expression': spec['forms_expression']
            }
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def get_last_form_repeat(spec, context):
    GetLastFormRepeatSpec.wrap(spec)

    if spec['case_id_expression'] is None:
        case_id_expression = {
            "type": "root_doc",
            "expression": {
                "type": "property_name",
                "property_name": "_id"
            }
        }
    else:
        case_id_expression = spec['case_id_expression']

    repeat_filters = []
    repeat_filters.append(
        {
            'type': 'boolean_expression',
            'operator': 'eq',
            'expression': {
                'type': 'property_path',
                'property_path': spec['case_id_path']
            },
            'property_value': case_id_expression
        }
    )

    if spec['repeat_filter'] is not None:
        repeat_filters.append(spec['repeat_filter'])

    spec = {
        'type': 'reduce_items',
        'aggregation_fn': 'last_item',
        'items_expression': {
            'type': 'filter_items',
            'filter_expression': {
                'type': 'and',
                'filters': repeat_filters
            },
            'items_expression': {
                'type': 'nested',
                'argument_expression': {
                    'type': 'reduce_items',
                    'aggregation_fn': 'last_item',
                    'items_expression': spec['forms_expression']
                },
                'value_expression': {
                    'type': 'property_path',
                    'datatype': 'array',
                    'property_path': spec['repeat_path']
                },
            }
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def get_case_history(spec, context):
    wrapped = GetCaseHistorySpec.wrap(spec)
    case_forms_expression = {
        'type': 'get_case_forms',
        'case_id_expression': wrapped.case_id_expression,
        'xmlns': wrapped.xmlns,
    }
    if spec['start_date'] or spec['end_date']:
        case_forms_expression['type'] = 'icds_get_case_forms_in_date'
        case_forms_expression['from_date_expression'] = wrapped.start_date
        case_forms_expression['to_date_expression'] = wrapped.end_date
    wrapped.configure(
        case_id_expression=ExpressionFactory.from_spec(wrapped.case_id_expression, context),
        case_forms_expression=ExpressionFactory.from_spec(case_forms_expression, context)
    )
    return wrapped


def get_case_history_by_date(spec, context):
    GetCaseHistoryByDateSpec.wrap(spec)

    if spec['case_id_expression'] is None:
        case_id_expression = {
            'expression': {
                'type': 'property_name',
                'property_name': '_id'
            },
            'type': 'root_doc'
        }
    else:
        case_id_expression = spec['case_id_expression']

    case_history_spec = {
        "type": "icds_get_case_history",
        "case_id_expression": case_id_expression
    }

    if spec['xmlns']:
        case_history_spec['xmlns'] = spec['xmlns']

    filters = []
    if spec['start_date'] is not None:
        start_date_filter = {
            'operator': 'gte',
            'expression': {
                'datatype': 'integer',
                'from_date_expression': spec['start_date'],
                'type': 'diff_days',
                'to_date_expression': {
                    'datatype': 'date',
                    'type': 'property_name',
                    'property_name': '@date_modified'
                }
            },
            'type': 'boolean_expression',
            'property_value': 0
        }
        filters.append(start_date_filter)
        case_history_spec['start_date'] = spec['start_date']
    if spec['end_date'] is not None:
        end_date_filter = {
            'operator': 'gte',
            'expression': {
                'datatype': 'integer',
                'from_date_expression': {
                    'datatype': 'date',
                    'type': 'property_name',
                    'property_name': '@date_modified'
                },
                'type': 'diff_days',
                'to_date_expression': spec['end_date']
            },
            'type': 'boolean_expression',
            'property_value': 0
        }
        filters.append(end_date_filter)
        case_history_spec['end_date'] = spec['end_date']
    if spec['filter'] is not None:
        filters.append(spec['filter'])

    if len(filters) > 0:
        case_history_spec = {
            "filter_expression": {
                "type": "and",
                "filters": filters
            },
            "type": "filter_items",
            "items_expression": case_history_spec
        }
    spec = {
        'type': 'sort_items',
        'sort_expression': {
            'datatype': 'date',
            'type': 'property_name',
            'property_name': '@date_modified',
        },
        "items_expression": case_history_spec
    }
    return ExpressionFactory.from_spec(spec, context)


def get_last_case_property_update(spec, context):
    GetLastCasePropertyUpdateSpec.wrap(spec)
    spec = {
        'type': 'nested',
        'argument_expression': {
            'type': 'reduce_items',
            'aggregation_fn': 'last_item',
            'items_expression': {
                'type': 'filter_items',
                'items_expression': {
                    'type': 'icds_get_case_history_by_date',
                    'case_id_expression': spec['case_id_expression'],
                    'start_date': spec['start_date'],
                    'end_date': spec['end_date'],
                    'filter': spec['filter'],
                    'xmlns': spec['xmlns'],
                },
                'filter_expression': {
                    'filter': {
                        'operator': 'in',
                        'type': 'boolean_expression',
                        'expression': {
                            'type': 'property_path',
                            'property_path': [
                                'update',
                                spec['case_property']
                            ]
                        },
                        'property_value': [
                            None
                        ]
                    },
                    'type': 'not'
                }
            }
        },
        'value_expression': {
            'type': 'property_path',
            'property_path': [
                'update',
                spec['case_property']
            ]
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def get_forms_in_date_expression(spec, context):
    wrapped = FormsInDateExpressionSpec.wrap(spec)
    from_date, to_date = None, None
    if wrapped.from_date_expression:
        from_date = ExpressionFactory.from_spec(wrapped.from_date_expression, context)
    if wrapped.to_date_expression:
        to_date = ExpressionFactory.from_spec(wrapped.to_date_expression, context)

    wrapped.configure(
        case_id_expression=ExpressionFactory.from_spec(wrapped.case_id_expression, context),
        from_date_expression=from_date,
        to_date_expression=to_date
    )
    return wrapped


def get_app_version(spec, context):
    wrapped = GetAppVersion.wrap(spec)
    wrapped.configure(
        app_version_string=ExpressionFactory.from_spec(wrapped.app_version_string, context)
    )
    return wrapped


def datetime_now(spec, context):
    return DateTimeNow.wrap(spec)


def boolean_question(spec, context):
    BooleanChoiceQuestion.wrap(spec)
    case_tuples = [(case, 1) for case in spec['true_values']]
    case_tuples.extend([(case, 0) for case in spec['false_values']])
    spec = {
        "type": "switch",
        "switch_on": spec['boolean_property'],
        "cases": {
            case: {
                "type": "constant",
                "constant": value
            }
            for case, value in case_tuples
        },
        "default": {
            "type": "constant",
            "constant": None if spec['nullable'] else 0
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def icds_user_location(spec, context):
    wrapped = ICDSUserLocation.wrap(spec)
    wrapped.configure(
        user_id_expression=ExpressionFactory.from_spec(wrapped.user_id_expression, context)
    )
    return wrapped


def awc_owner_id(spec, context):
    wrapped = AWCOwnerId.wrap(spec)
    wrapped.configure(
        case_id_expression=ExpressionFactory.from_spec(wrapped.case_id_expression, context)
    )
    return wrapped
