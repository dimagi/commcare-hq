from corehq.apps.userreports.expressions.factory import ExpressionFactory
from jsonobject.base_properties import DefaultProperty
from corehq.apps.userreports.specs import TypeProperty
from corehq.apps.userreports.expressions.getters import transform_date
from dimagi.ext.jsonobject import JsonObject, ListProperty, StringProperty


NUM_FUTURE_MONTHS = 3


CUSTOM_UCR_EXPRESSIONS = [
    ('ext_diff_calendar_months', 'custom.ucr_ext.expressions.diff_calendar_months'),
    ('ext_root_property_name', 'custom.ucr_ext.expressions.root_property_name'),
    ('ext_iterate_from_opened_date', 'custom.ucr_ext.expressions.iterate_from_opened_date'),
    ('ext_month_start', 'custom.ucr_ext.expressions.month_start'),
    ('ext_month_end', 'custom.ucr_ext.expressions.month_end'),
    ('ext_parent_id', 'custom.ucr_ext.expressions.parent_id'),
    ('ext_open_in_month', 'custom.ucr_ext.expressions.open_in_month'),
    ('ext_get_case_forms_by_date', 'custom.ucr_ext.expressions.get_case_forms_by_date'),
]


class DiffCalendarMonthsExpressionSpec(JsonObject):
    type = TypeProperty('ext_diff_calendar_months')
    from_date_expression = DefaultProperty(required=True)
    to_date_expression = DefaultProperty(required=True)

    def configure(self, from_date_expression, to_date_expression):
        self._from_date_expression = from_date_expression
        self._to_date_expression = to_date_expression

    def __call__(self, item, context=None):
        from_date_val = transform_date(self._from_date_expression(item, context))
        to_date_val = transform_date(self._to_date_expression(item, context))
        if from_date_val is not None and to_date_val is not None:
            return ((to_date_val.year - from_date_val.year) * 12) + to_date_val.month - from_date_val.month
        return None


class RootPropertyNameSpec(JsonObject):
    type = TypeProperty('ext_root_property_name')
    property_name = StringProperty(required=True)
    datatype = StringProperty(required=False)


class GetCaseFormsByDateSpec(JsonObject):
    type = TypeProperty('ext_get_case_forms_by_date')
    case_id_expression = DefaultProperty(required=False)
    xmlns = ListProperty(required=False)
    start_date = DefaultProperty(required=False)
    end_date = DefaultProperty(required=False)
    form_filter = DefaultProperty(required=False)


def diff_calendar_months(spec, context):
    wrapped = DiffCalendarMonthsExpressionSpec.wrap(spec)
    wrapped.configure(
        from_date_expression=ExpressionFactory.from_spec(wrapped.from_date_expression, context),
        to_date_expression=ExpressionFactory.from_spec(wrapped.to_date_expression, context),
    )
    return wrapped


def root_property_name(spec, context):
    RootPropertyNameSpec.wrap(spec)
    spec = {
        'type': 'root_doc',
        'expression': {
            'type': 'property_name',
            'property_name': spec['property_name'],
            'datatype': spec['datatype']
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def iterate_from_opened_date(spec, context):
    spec = {
        'type': 'evaluator',
        'datatype': 'array',
        'context_variables': {
            'count': {
                'type': 'conditional',
                'datatype': 'integer',
                'test': {
                    'type': 'boolean_expression',
                    'operator': 'eq',
                    'expression': {
                        'type': 'property_name',
                        'property_name': 'closed',
                        'datatype': 'string',
                    },
                    'property_value': 'True'
                },
                'expression_if_true': {
                    'type': 'evaluator',
                    'datatype': 'integer',
                    'context_variables': {
                        'difference': {
                            'type': 'ext_diff_calendar_months',
                            'from_date_expression': {
                                'type': 'month_start_date',
                                'date_expression': {
                                    'type': 'property_name',
                                    'datatype': 'date',
                                    'property_name': 'opened_on'
                                },
                            },
                            'to_date_expression': {
                                'type': 'month_start_date',
                                'date_expression': {
                                    'type': 'property_name',
                                    'datatype': 'date',
                                    'property_name': 'closed_on'
                                },
                            }
                        }
                    },
                    'statement': 'difference + 1'
                },
                'expression_if_false': {
                    'type': 'evaluator',
                    'datatype': 'integer',
                    'context_variables': {
                        'difference': {
                            'type': 'ext_diff_calendar_months',
                            'from_date_expression': {
                                'type': 'month_start_date',
                                'date_expression': {
                                    'type': 'property_name',
                                    'datatype': 'date',
                                    'property_name': 'opened_on'
                                },
                            },
                            'to_date_expression': {
                                'type': 'month_start_date',
                                'date_expression': {
                                    'type': 'property_name',
                                    'datatype': 'date',
                                    'property_name': 'modified_on'
                                },
                            }
                        }
                    },
                    'statement': 'difference + 1 + ' + str(NUM_FUTURE_MONTHS)
                }
            }
        },
        'statement': 'range(count)'
    }
    return ExpressionFactory.from_spec(spec, context)


def month_start(spec, context):
    spec = {
        'type': 'month_start_date',
        'date_expression': {
            'type': 'add_months',
            'date_expression': {
                'type': 'ext_root_property_name',
                'property_name': 'opened_on',
            },
            'months_expression': {
                'type': 'base_iteration_number'
            }
        }
    }
    return ExpressionFactory.from_spec(spec, context)


def month_end(spec, context):
    spec = {
        'type': 'month_end_date',
        'date_expression': {
            'type': 'add_months',
            'date_expression': {
                'type': 'ext_root_property_name',
                'property_name': 'opened_on',
            },
            'months_expression': {
                'type': 'base_iteration_number'
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
                    'type': 'ext_root_property_name',
                    'property_name': 'indices',
                    'datatype': 'array',
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
                            'type': 'ext_root_property_name',
                            'property_name': 'opened_on',
                            'datatype': 'date',
                        },
                        'to_date_expression': {
                            'type': 'ext_month_end',
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
                                'type': 'ext_root_property_name',
                                'property_name': 'closed',
                                'datatype': 'string',
                            },
                            'property_value': 'False'
                        },
                        {
                            'type': 'boolean_expression',
                            'operator': 'gte',
                            'expression': {
                                'type': 'diff_days',
                                'from_date_expression': {
                                    'type': 'ext_month_start',
                                },
                                'to_date_expression': {
                                    'type': 'ext_root_property_name',
                                    'property_name': 'closed_on',
                                    'datatype': 'date',
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
            "type": "ext_root_property_name",
            "property_name": "_id",
        }
    else:
        case_id_expression = spec['case_id_expression']

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
                    'type': 'property_path',
                    'property_path': [
                        'form',
                        'meta',
                        'timeEnd'
                    ]
                }
            },
            'type': 'boolean_expression',
            'property_value': 0
        }
        filters.append(start_date_filter)
    if spec['end_date'] is not None:
        end_date_filter = {
            'operator': 'gte',
            'expression': {
                'datatype': 'integer',
                'from_date_expression': {
                    'datatype': 'date',
                    'type': 'property_path',
                    'property_path': [
                        'form',
                        'meta',
                        'timeEnd'
                    ]
                },
                'type': 'diff_days',
                'to_date_expression': spec['end_date']
            },
            'type': 'boolean_expression',
            'property_value': 0
        }
        filters.append(end_date_filter)
    if spec['xmlns'] is not None and len(spec['xmlns']) > 0:
        xmlns_filters = []
        for x in spec['xmlns']:
                x_filter = {
                    "operator": "eq",
                    "type": "boolean_expression",
                    "expression": {
                        "datatype": "string",
                        "type": "property_name",
                        "property_name": "xmlns"
                    },
                    "property_value": x
                }
                xmlns_filters.append(x_filter)
        xmlns_filter = {
            "type": "or",
            "filters": xmlns_filters
        }
        filters.append(xmlns_filter)
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
                "items_expression": {
                    "type": "get_case_forms",
                    "case_id_expression": case_id_expression
                }
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
            "items_expression": {
                "type": "get_case_forms",
                "case_id_expression": case_id_expression
            }
        }
    return ExpressionFactory.from_spec(spec, context)
