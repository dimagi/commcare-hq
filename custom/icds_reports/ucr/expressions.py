from corehq.apps.userreports.expressions.factory import ExpressionFactory
from jsonobject.base_properties import DefaultProperty
from corehq.apps.userreports.specs import TypeProperty
from dimagi.ext.jsonobject import JsonObject, ListProperty


CUSTOM_UCR_EXPRESSIONS = [
    ('icds_month_start', 'custom.icds_reports.ucr.expressions.month_start'),
    ('icds_month_end', 'custom.icds_reports.ucr.expressions.month_end'),
    ('icds_parent_id', 'custom.icds_reports.ucr.expressions.parent_id'),
    ('icds_parent_parent_id', 'custom.icds_reports.ucr.expressions.parent_parent_id'),
    ('icds_open_in_month', 'custom.icds_reports.ucr.expressions.open_in_month'),
    ('icds_get_case_forms_by_date', 'custom.icds_reports.ucr.expressions.get_case_forms_by_date'),
    ('icds_ccs_alive_in_month', 'custom.icds_reports.ucr.expressions.ccs_alive_in_month'),
    ('icds_ccs_pregnant', 'custom.icds_reports.ucr.expressions.ccs_pregnant'),
    ('icds_ccs_lactating', 'custom.icds_reports.ucr.expressions.ccs_lactating'),
]


class MonthStartSpec(JsonObject):
    type = TypeProperty('icds_month_start')


class MonthEndSpec(JsonObject):
    type = TypeProperty('icds_month_end')


class ParentIdSpec(JsonObject):
    type = TypeProperty('icds_parent_id')


class ParentParentIdSpec(JsonObject):
    type = TypeProperty('icds_parent_parent_id')


class OpenInMonthSpec(JsonObject):
    type = TypeProperty('icds_open_in_month')


class GetCaseFormsByDateSpec(JsonObject):
    type = TypeProperty('icds_get_case_forms_by_date')
    case_id_expression = DefaultProperty(required=True)
    xmlns = ListProperty(required=False)
    start_date = DefaultProperty(required=False)
    end_date = DefaultProperty(required=False)
    form_filter = DefaultProperty(required=False)


class CCSAliveInMonthSpec(JsonObject):
    type = TypeProperty('icds_ccs_alive_in_month')


class CCSPregnantSpec(JsonObject):
    type = TypeProperty('icds_ccs_pregnant')


class CCSLactatingSpec(JsonObject):
    type = TypeProperty('icds_ccs_lactating')


def month_start(spec, context):
    # fix offset to 3 months in past
    MonthStartSpec.wrap(spec)
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
    MonthEndSpec.wrap(spec)
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
    ParentIdSpec.wrap(spec)
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
    ParentParentIdSpec.wrap(spec)
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
    OpenInMonthSpec.wrap(spec)
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
                            'offset': 3
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
                                    'offset': 3
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
                    "case_id_expression": spec['case_id_expression']
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
                "case_id_expression": spec['case_id_expression']
            }
        }
    return ExpressionFactory.from_spec(spec, context)


def ccs_alive_in_month(spec, context):
    CCSAliveInMonthSpec.wrap(spec)
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
    CCSPregnantSpec.wrap(spec)
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
                        'type': 'icds_ccs_alive_in_month'
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
    CCSLactatingSpec.wrap(spec)
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
                        'type': 'icds_ccs_alive_in_month'
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
