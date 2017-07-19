from datetime import datetime
from jsonobject.base_properties import DefaultProperty
from casexml.apps.case.xform import extract_case_blocks
from corehq.apps.es.forms import FormES
from corehq.apps.userreports.const import XFORM_CACHE_KEY_PREFIX
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import TypeProperty
from corehq.elastic import mget_query
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from dimagi.ext.jsonobject import JsonObject, ListProperty, StringProperty, DictProperty, BooleanProperty


CUSTOM_UCR_EXPRESSIONS = [
    ('icds_month_start', 'custom.icds_reports.ucr.expressions.month_start'),
    ('icds_month_end', 'custom.icds_reports.ucr.expressions.month_end'),
    ('icds_parent_id', 'custom.icds_reports.ucr.expressions.parent_id'),
    ('icds_parent_parent_id', 'custom.icds_reports.ucr.expressions.parent_parent_id'),
    ('icds_open_in_month', 'custom.icds_reports.ucr.expressions.open_in_month'),
    ('icds_get_case_forms_by_date', 'custom.icds_reports.ucr.expressions.get_case_forms_by_date'),
    ('icds_get_all_forms_repeats', 'custom.icds_reports.ucr.expressions.get_all_forms_repeats'),
    ('icds_get_last_form_repeat', 'custom.icds_reports.ucr.expressions.get_last_form_repeat'),
    ('icds_alive_in_month', 'custom.icds_reports.ucr.expressions.alive_in_month'),
    ('icds_ccs_pregnant', 'custom.icds_reports.ucr.expressions.ccs_pregnant'),
    ('icds_ccs_lactating', 'custom.icds_reports.ucr.expressions.ccs_lactating'),
    ('icds_child_age_in_days', 'custom.icds_reports.ucr.expressions.child_age_in_days'),
    ('icds_child_age_in_months_month_start',
     'custom.icds_reports.ucr.expressions.child_age_in_months_month_start'),
    ('icds_child_age_in_months_month_end', 'custom.icds_reports.ucr.expressions.child_age_in_months_month_end'),
    ('icds_child_valid_in_month', 'custom.icds_reports.ucr.expressions.child_valid_in_month'),
    ('icds_get_case_history', 'custom.icds_reports.ucr.expressions.get_case_history'),
    ('icds_get_case_history_by_date', 'custom.icds_reports.ucr.expressions.get_case_history_by_date'),
    ('icds_get_last_case_property_update', 'custom.icds_reports.ucr.expressions.get_last_case_property_update'),
    ('icds_get_case_forms_in_date', 'custom.icds_reports.ucr.expressions.get_forms_in_date_expression'),
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

        # TODO(Sheel/Emord) looks like this is only used when getting the last
        # property update. maybe this could be optimized sort by received_on
        # and stop looking at forms once it finds the update
        case_history = []
        for f in forms:
            case_blocks = extract_case_blocks(f)
            if case_blocks:
                case_history.append(
                    next(case_block for case_block in case_blocks
                         if case_block['@case_id'] == case_id))
        context.set_cache_value(cache_key, case_history)
        return case_history


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


class FormsInDateExpressionSpec(JsonObject):
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

        xform_ids = self._get_case_form_ids(case_id, context)
        # TODO(Emord) this will eventually break down when cases have a lot of
        # forms associated with them. perhaps change to intersecting two sets
        xforms = self._get_filtered_forms_from_es(case_id, xform_ids, context)
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

        form_ids = [x['_id'] for x in xforms]
        xforms = FormAccessors(domain).get_forms(form_ids)
        xforms = [self._get_form_json(f, context) for f in xforms if f.domain == domain]

        context.set_cache_value(cache_key, xforms)
        return xforms

    def _get_filtered_forms_from_es(self, case_id, xform_ids, context):
        cache_key = (self.__class__.__name__, 'es_helper', case_id, tuple(xform_ids))
        if context.get_cache_value(cache_key) is not None:
            return context.get_cache_value(cache_key)

        def _transform_time_end(xform):
            xform = xform.get('_source', {})
            if not xform.get('xmlns', None):
                return None
            try:
                time = xform['form']['meta']['timeEnd']
            except KeyError:
                return None

            xform['timeEnd'] = datetime.strptime(time, '%Y-%m-%dT%H:%M:%S.%fZ').date()
            return xform

        forms = mget_query('forms', xform_ids, ['form.meta.timeEnd', 'xmlns', '_id'])
        forms = filter(None, map(_transform_time_end, forms))
        context.set_cache_value(cache_key, forms)
        return forms

    def _get_case_form_ids(self, case_id, context):
        cache_key = (self.__class__.__name__, 'helper', case_id)
        if context.get_cache_value(cache_key) is not None:
            return context.get_cache_value(cache_key)

        domain = context.root_doc['domain']
        xform_ids = CaseAccessors(domain).get_case_xform_ids(case_id)
        context.set_cache_value(cache_key, xform_ids)
        return xform_ids

    def _get_form_json(self, form, context):
        cache_key = (XFORM_CACHE_KEY_PREFIX, form.get_id)
        if context.get_cache_value(cache_key) is not None:
            return context.get_cache_value(cache_key)

        form_json = form.to_json()
        context.set_cache_value(cache_key, form_json)
        return form_json


def month_start(spec, context):
    # fix offset to 3 months in past
    spec = {
        'type': 'month_start_date',
        'date_expression': {
            'date_expression': {
                'expression': {
                    'type': 'property_name',
                    'property_name': 'modified_on'
                },
                'type': 'root_doc'
            },
            'type': 'add_months',
            'months_expression': {
                'type': 'evaluator',
                'context_variables': {
                    'iteration': {
                        'type': 'base_iteration_number'
                    }
                },
                'statement': 'iteration - 3'
            }
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def month_end(spec, context):
    # fix offset to 3 months in past
    spec = {
        'type': 'month_end_date',
        'date_expression': {
            'date_expression': {
                'expression': {
                    'type': 'property_name',
                    'property_name': 'modified_on'
                },
                'type': 'root_doc'
            },
            'type': 'add_months',
            'months_expression': {
                'type': 'evaluator',
                'context_variables': {
                    'iteration': {
                        'type': 'base_iteration_number'
                    }
                },
                'statement': 'iteration - 3'
            }
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def parent_id(spec, context):
    spec = {
        'type': 'nested',
        'argument_expression': {
            'type': 'array_index',
            'array_expression': {
                'type': 'filter_items',
                'items_expression': {
                    'type': 'root_doc',
                    'expression': {
                        'datatype': 'array',
                        'type': 'property_name',
                        'property_name': 'indices'
                    }
                },
                'filter_expression': {
                    'type': 'boolean_expression',
                    'operator': 'eq',
                    'property_value': 'parent',
                    'expression': {
                        'type': 'property_name',
                        'property_name': 'identifier'
                    }
                }
            },
            'index_expression': {
                'type': 'constant',
                'constant': 0
            }
        },
        'value_expression': {
            'type': 'property_name',
            'property_name': 'referenced_id'
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def parent_parent_id(spec, context):
    spec = {
        'type': 'related_doc',
        'related_doc_type': 'CommCareCase',
        'doc_id_expression': {
            'type': 'icds_parent_id'
        },
        'value_expression': {
            'type': 'nested',
            'argument_expression': {
                'type': 'array_index',
                'array_expression': {
                    'type': 'filter_items',
                    'items_expression': {
                        'type': 'root_doc',
                        'expression': {
                            'datatype': 'array',
                            'type': 'property_name',
                            'property_name': 'indices'
                        }
                    },
                    'filter_expression': {
                        'type': 'boolean_expression',
                        'operator': 'eq',
                        'property_value': 'parent',
                        'expression': {
                            'type': 'property_name',
                            'property_name': 'identifier'
                        }
                    }
                },
                'index_expression': {
                    'type': 'constant',
                    'constant': 0
                }
            },
            'value_expression': {
                'type': 'property_name',
                'property_name': 'referenced_id'
            }
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def open_in_month(spec, context):
    spec = {
        'type': 'conditional',
        'test': {
            'type': 'and',
            'filters': [
                {
                    'type': 'boolean_expression',
                    'operator': 'gte',
                    'expression': {
                        'type': 'diff_days',
                        'from_date_expression': {
                            'expression': {
                                'datatype': 'date',
                                'type': 'property_name',
                                'property_name': 'opened_on'
                            },
                            'type': 'root_doc'
                        },
                        'to_date_expression': {
                            'type': 'icds_month_end',
                        }
                    },
                    'property_value': 0
                },
                {
                    'type': 'or',
                    'filters': [
                        {
                            'type': 'boolean_expression',
                            'operator': 'eq',
                            'expression': {
                                'expression': {
                                    'datatype': 'string',
                                    'type': 'property_name',
                                    'property_name': 'closed'
                                },
                                'type': 'root_doc'
                            },
                            'property_value': 'False'
                        },
                        {
                            'type': 'boolean_expression',
                            'operator': 'gte',
                            'expression': {
                                'type': 'diff_days',
                                'from_date_expression': {
                                    'type': 'icds_month_start',
                                },
                                'to_date_expression': {
                                    'expression': {
                                        'datatype': 'date',
                                        'type': 'property_name',
                                        'property_name': 'closed_on'
                                    },
                                    'type': 'root_doc'
                                }
                            },
                            'property_value': 0
                        }
                    ]
                }
            ]
        },
        'expression_if_true': {
            'type': 'constant',
            'constant': 'yes'
        },
        'expression_if_false': {
            'type': 'constant',
            'constant': 'no'
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

    get_case_forms_expression = {
        "type": "icds_get_case_forms_in_date",
        "case_id_expression": case_id_expression
    }
    filters = []
    if spec['start_date'] is not None:
        get_case_forms_expression['from_date_expression'] = spec['start_date']
    if spec['end_date'] is not None:
        get_case_forms_expression['to_date_expression'] = spec['end_date']
    if spec['xmlns']:
        get_case_forms_expression['xmlns'] = spec['xmlns']
    if spec['form_filter'] is not None:
        filters.append(spec['form_filter'])

    if len(filters) > 0:
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
            "items_expression": {
                "filter_expression": {
                    "type": "and",
                    "filters": filters
                },
                "type": "filter_items",
                "items_expression": get_case_forms_expression
            }
        }
    else:
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
            "items_expression": get_case_forms_expression
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


def alive_in_month(spec, context):
    spec = {
        'type': 'conditional',
        'test': {
            'type': 'or',
            'filters': [
                {
                    'operator': 'in',
                    'expression': {
                        'value_expression': {
                            'datatype': 'date',
                            'type': 'property_name',
                            'property_name': 'date_death'
                        },
                        'type': 'related_doc',
                        'related_doc_type': 'CommCareCase',
                        'doc_id_expression': {
                            'type': 'icds_parent_id'
                        }
                    },
                    'type': 'boolean_expression',
                    'property_value': [
                        '',
                        None
                    ]
                },
                {
                    'operator': 'gte',
                    'expression': {
                        'from_date_expression': {
                            'type': 'icds_month_start'
                        },
                        'type': 'diff_days',
                        'to_date_expression': {
                            'value_expression': {
                                'datatype': 'date',
                                'type': 'property_name',
                                'property_name': 'date_death'
                            },
                            'type': 'related_doc',
                            'related_doc_type': 'CommCareCase',
                            'doc_id_expression': {
                                'type': 'icds_parent_id'
                            }
                        }
                    },
                    'type': 'boolean_expression',
                    'property_value': 0
                }
            ]
        },
        'expression_if_true': {
            'type': 'constant',
            'constant': 'yes'
        },
        'expression_if_false': {
            'type': 'constant',
            'constant': 'no'
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def ccs_pregnant(spec, context):
    spec = {
        'type': 'conditional',
        'test': {
            'type': 'and',
            'filters': [
                {
                    'type': 'boolean_expression',
                    'operator': 'eq',
                    'expression': {
                        'type': 'icds_open_in_month'
                    },
                    'property_value': 'yes'
                },
                {
                    'type': 'boolean_expression',
                    'operator': 'eq',
                    'expression': {
                        'type': 'icds_alive_in_month'
                    },
                    'property_value': 'yes'
                },
                {
                    'type': 'or',
                    'filters': [
                        {
                            'operator': 'in',
                            'type': 'boolean_expression',
                            'expression': {
                                'type': 'root_doc',
                                'expression': {
                                    'datatype': 'date',
                                    'type': 'property_name',
                                    'property_name': 'add'
                                }
                            },
                            'property_value': [
                                '',
                                None
                            ]
                        },
                        {
                            'type': 'boolean_expression',
                            'operator': 'gt',
                            'property_value': 0,
                            'expression': {
                                'type': 'diff_days',
                                'to_date_expression': {
                                    'type': 'root_doc',
                                    'expression': {
                                        'datatype': 'date',
                                        'type': 'property_name',
                                        'property_name': 'add'
                                    }
                                },
                                'from_date_expression': {
                                    'type': 'icds_month_end'
                                }
                            }
                        }
                    ]
                }
            ]
        },
        'expression_if_true': {
            'type': 'constant',
            'constant': 'yes'
        },
        'expression_if_false': {
            'type': 'constant',
            'constant': 'no'
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def ccs_lactating(spec, context):
    spec = {
        'type': 'conditional',
        'test': {
            'type': 'and',
            'filters': [
                {
                    'type': 'boolean_expression',
                    'operator': 'eq',
                    'expression': {
                        'type': 'icds_open_in_month'
                    },
                    'property_value': 'yes'
                },
                {
                    'type': 'boolean_expression',
                    'operator': 'eq',
                    'expression': {
                        'type': 'icds_alive_in_month'
                    },
                    'property_value': 'yes'
                },
                {
                    'type': 'not',
                    'filter': {
                        'operator': 'in',
                        'type': 'boolean_expression',
                        'expression': {
                            'type': 'root_doc',
                            'expression': {
                                'datatype': 'date',
                                'type': 'property_name',
                                'property_name': 'add'
                            }
                        },
                        'property_value': [
                            '',
                            None
                        ]
                    }
                },
                {
                    'type': 'boolean_expression',
                    'operator': 'gte',
                    'property_value': 0,
                    'expression': {
                        'type': 'diff_days',
                        'to_date_expression': {
                            'type': 'icds_month_end'
                        },
                        'from_date_expression': {
                            'type': 'root_doc',
                            'expression': {
                                'datatype': 'date',
                                'type': 'property_name',
                                'property_name': 'add'
                            }
                        }
                    }
                },
                {
                    'type': 'boolean_expression',
                    'operator': 'lte',
                    'property_value': 183,
                    'expression': {
                        'type': 'diff_days',
                        'from_date_expression': {
                            'type': 'root_doc',
                            'expression': {
                                'datatype': 'date',
                                'type': 'property_name',
                                'property_name': 'add'
                            }
                        },
                        'to_date_expression': {
                            'type': 'icds_month_start'
                        }
                    }
                }
            ]
        },
        'expression_if_true': {
            'type': 'constant',
            'constant': 'yes'
        },
        'expression_if_false': {
            'type': 'constant',
            'constant': 'no'
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def child_age_in_days(spec, context):
    spec = {
        'type': 'diff_days',
        'from_date_expression': {
            'type': 'related_doc',
            'related_doc_type': 'CommCareCase',
            'doc_id_expression': {
                'type': 'icds_parent_id'
            },
            'value_expression': {
                'datatype': 'date',
                'property_name': 'dob',
                'type': 'property_name'
            }
        },
        'to_date_expression': {
            'type': 'icds_month_end'
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def child_age_in_months_month_end(spec, context):
    spec = {
        'type': 'evaluator',
        'statement': 'age_in_days / 30.4',
        'context_variables': {
            'age_in_days': {
                'type': 'icds_child_age_in_days'
            }
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def child_age_in_months_month_start(spec, context):
    spec = {
        'type': 'evaluator',
        'statement': 'age_in_days / 30.4',
        'context_variables': {
            'age_in_days': {
                'type': 'diff_days',
                'from_date_expression': {
                    'type': 'related_doc',
                    'related_doc_type': 'CommCareCase',
                    'doc_id_expression': {
                        'type': 'icds_parent_id'
                    },
                    'value_expression': {
                        'datatype': 'date',
                        'property_name': 'dob',
                        'type': 'property_name'
                    }
                },
                'to_date_expression': {
                    'type': 'icds_month_start'
                }
            }
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def child_valid_in_month(spec, context):
    spec = {
        'type': 'conditional',
        'test': {
            "type": "and",
            "filters": [
                {
                    'type': 'boolean_expression',
                    'operator': 'eq',
                    'property_value': 'yes',
                    'expression': {
                        'type': 'icds_alive_in_month'
                    }
                },
                {
                    'type': 'boolean_expression',
                    'operator': 'eq',
                    'property_value': 'yes',
                    'expression': {
                        'type': 'icds_open_in_month'
                    }
                },
                {
                    "type": "not",
                    "filter": {
                        "operator": "in",
                        "type": "boolean_expression",
                        "expression": {
                            "type": "icds_child_age_in_months_month_start"
                        },
                        "property_value": [
                            "",
                            None
                        ]
                    }
                },
                {
                    "type": "boolean_expression",
                    "operator": "lte",
                    "property_value": 72,
                    "expression": {
                        "type": "icds_child_age_in_months_month_start"
                    }
                }
            ]
        },
        'expression_if_true': {
            'type': 'constant',
            'constant': 'yes'
        },
        'expression_if_false': {
            'type': 'constant',
            'constant': 'no'
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
