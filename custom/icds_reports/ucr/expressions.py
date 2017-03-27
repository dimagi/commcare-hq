import hashlib
from jsonobject.base_properties import DefaultProperty
from casexml.apps.case.xform import extract_case_blocks
from corehq.apps.es.forms import FormES
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import TypeProperty
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

    def configure(self, case_id_expression, case_forms_expression):
        self._case_id_expression = case_id_expression
        self._case_forms_expression = case_forms_expression

    def __call__(self, item, context=None):
        case_id = self._case_id_expression(item, context)
        if not case_id:
            return []

        cache_key = (self.__class__.__name__, case_id)
        if context.get_cache_value(cache_key) is not None:
            return context.get_cache_value(cache_key)

        forms = self._case_forms_expression(item, context)

        case_history = []
        for f in forms:
            case_blocks = extract_case_blocks(f)
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


class GetLastCasePropertyUpdateSpec(JsonObject):
    type = TypeProperty('icds_get_last_case_property_update')
    case_property = StringProperty(required=True)
    case_id_expression = DefaultProperty(required=False)
    start_date = DefaultProperty(required=False)
    end_date = DefaultProperty(required=False)
    filter = DefaultProperty(required=False)


class FormsInDateExpressionSpec(JsonObject):
    type = TypeProperty('icds_get_case_forms_in_date')
    case_id_expression = DefaultProperty(required=True)
    xmlns = ListProperty(required=False)
    from_date_expression = DictProperty(required=True)
    to_date_expression = DictProperty(required=True)
    count = BooleanProperty(default=False)

    def configure(self, case_id_expression, from_date_expression, to_date_expression):
        self._case_id_expression = case_id_expression
        self._from_date_expression = from_date_expression
        self._to_date_expression = to_date_expression

    def __call__(self, item, context=None):
        case_id = self._case_id_expression(item, context)
        from_date = self._from_date_expression(item, context)
        to_date = self._to_date_expression(item, context)

        if not case_id:
            return []

        assert context.root_doc['domain']
        return self._get_forms(case_id, from_date, to_date, context)

    def _get_forms(self, case_id, from_date, to_date, context):
        domain = context.root_doc['domain']
        cache_hash = "{}{}{}".format(from_date.toordinal(), to_date.toordinal(), self.count)
        if self.xmlns:
            cache_hash += ''.join(self.xmlns)

        cache_hash = hashlib.md5(cache_hash).hexdigest()[:4]

        cache_key = (self.__class__.__name__, case_id, cache_hash)
        if context.get_cache_value(cache_key) is not None:
            return context.get_cache_value(cache_key)

        xform_ids = CaseAccessors(domain).get_case_xform_ids(case_id)
        # TODO(Emord) this will eventually break down when cases have a lot of
        # forms associated with them. perhaps change to intersecting two sets
        query = (
            FormES()
            .domain(domain)
            .completed(gte=from_date, lte=to_date)
            .doc_id(xform_ids)
        )
        if self.xmlns:
            query = query.xmlns(self.xmlns)
        if self.count:
            count = query.count()
            context.set_cache_value(cache_key, count)
            return count

        form_ids = query.get_ids()
        xforms = FormAccessors(domain).get_forms(form_ids)
        xforms = [f.to_json() for f in xforms if f.domain == domain]

        context.set_cache_value(cache_key, xforms)
        return xforms


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
    wrapped.configure(
        case_id_expression=ExpressionFactory.from_spec(wrapped.case_id_expression, context),
        case_forms_expression=ExpressionFactory.from_spec({
            'type': 'get_case_forms',
            'case_id_expression': wrapped.case_id_expression
        }, context)
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
    if spec['filter'] is not None:
        filters.append(spec['filter'])

    spec = {
        "type": "icds_get_case_history",
        "case_id_expression": case_id_expression
    }
    if len(filters) > 0:
        spec = {
            "filter_expression": {
                "type": "and",
                "filters": filters
            },
            "type": "filter_items",
            "items_expression": spec
        }
    spec = {
        'type': 'sort_items',
        'sort_expression': {
            'datatype': 'date',
            'type': 'property_name',
            'property_name': '@date_modified',
        },
        "items_expression": spec
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
    wrapped.configure(
        case_id_expression=ExpressionFactory.from_spec(wrapped.case_id_expression, context),
        from_date_expression=ExpressionFactory.from_spec(wrapped.from_date_expression, context),
        to_date_expression=ExpressionFactory.from_spec(wrapped.to_date_expression, context)
    )
    return wrapped
