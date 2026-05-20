import pytest
import re

from calculate_keep import (
    _handle,
    _parse_linked_domains,
    COL_ENVIRONMENT,
    COL_DOMAIN_NAME,
    COL_SERVICE_TYPE,
    COL_PLAN_NAME,
    COL_CASE_SEARCH_ENABLED,
    COL_LINKED_DOMAIN_NAMES,
    COL_KEEP,
    COL_REASON,
)

DOMAIN_NAME = 'my_domain'
DOMAIN_NAME_QA = 'my_QA_domain'
SERVICE_TYPE_KEEP = 'PRODUCT'
SERVICE_TYPE_DO_NOT_KEEP = 'INTERNAL'
PLAN_NAME_KEEP = 'keep plan'
PLAN_NAME_DO_NOT_KEEP = 'test plan'

KEEP_DOMAINS = {DOMAIN_NAME_QA}
KEEP_SERVICE_TYPES = {
    SERVICE_TYPE_KEEP: True,
    SERVICE_TYPE_DO_NOT_KEEP: False
}
KEEP_PLAN_NAMES = {
    PLAN_NAME_KEEP: True,
    PLAN_NAME_DO_NOT_KEEP: False
}

ROW_DICT = {
    COL_ENVIRONMENT: 'test',
    COL_DOMAIN_NAME: DOMAIN_NAME,
    COL_SERVICE_TYPE: SERVICE_TYPE_DO_NOT_KEEP,
    COL_PLAN_NAME: PLAN_NAME_DO_NOT_KEEP,
    COL_CASE_SEARCH_ENABLED: 'FALSE',
    COL_LINKED_DOMAIN_NAMES: '',
}

SERVICE_PLAN_KEEP_ENABLED = {
    COL_SERVICE_TYPE: SERVICE_TYPE_KEEP,
    COL_PLAN_NAME: PLAN_NAME_KEEP,
    COL_CASE_SEARCH_ENABLED: 'TRUE',
}

ROW_UPSTREAM = {
    COL_DOMAIN_NAME: 'domain_upstream',
    COL_LINKED_DOMAIN_NAMES: 'domain_downstream,domain_downstream_2'
}

ROW_DOWNSTREAM = {
    COL_DOMAIN_NAME: 'domain_downstream'
}

ROW_DOWNSTREAM_2 = {
    COL_DOMAIN_NAME: 'domain_downstream_2'
}

ROW_KEEP_QA = {
    COL_REASON: 'qa domain'
}

ROW_KEEP_PRODUCTION = {
    COL_REASON: 'production domain'
}

ROW_KEEP_DOWNSTREAM = {
    COL_REASON: 'has downstream keep'
}

ROW_KEEP_UPSTREAM = {
    COL_REASON: 'has upstream keep'
}

RESULT_DICT_KEEP = {
    **ROW_DICT,
    COL_KEEP: 'TRUE'
}

RESULT_DICT_DO_NOT_KEEP = {
    **ROW_DICT,
    COL_KEEP: 'FALSE',
    COL_REASON: ''
}


def test_empty_inputs():
    assert _handle([], set(), {}, {}) == []

def test_keep_domain_true():
    assert _handle(
        usage_rows = [{
            **ROW_DICT,
            COL_DOMAIN_NAME: DOMAIN_NAME_QA
        }],
        keep_domains = KEEP_DOMAINS,
        plan_keep = KEEP_PLAN_NAMES,
        service_keep = KEEP_SERVICE_TYPES
    ) == [{
        **RESULT_DICT_KEEP,
        COL_DOMAIN_NAME: DOMAIN_NAME_QA,
        **ROW_KEEP_QA
    }]

def test_keep_domain_false():
    assert _handle(
        usage_rows = [ROW_DICT],
        keep_domains = KEEP_DOMAINS,
        plan_keep = KEEP_PLAN_NAMES,
        service_keep = KEEP_SERVICE_TYPES
    ) == [RESULT_DICT_DO_NOT_KEEP]

def test_cs_enabled_only_false():
    assert _handle(
        usage_rows = [{
            **ROW_DICT,
            COL_CASE_SEARCH_ENABLED: 'TRUE'
        }],
        keep_domains = KEEP_DOMAINS,
        plan_keep = KEEP_PLAN_NAMES,
        service_keep = KEEP_SERVICE_TYPES
    ) == [{
        **RESULT_DICT_DO_NOT_KEEP,
        COL_CASE_SEARCH_ENABLED: 'TRUE'
    }]

def test_serivce_type_only_false():
    assert _handle(
        usage_rows = [{
            **ROW_DICT,
            COL_SERVICE_TYPE: SERVICE_TYPE_KEEP
        }],
        keep_domains = KEEP_DOMAINS,
        plan_keep = KEEP_PLAN_NAMES,
        service_keep = KEEP_SERVICE_TYPES
    ) == [{
        **RESULT_DICT_DO_NOT_KEEP,
        COL_SERVICE_TYPE: SERVICE_TYPE_KEEP
    }]

def test_plan_name_only_false():
    assert _handle(
        usage_rows = [{
            **ROW_DICT,
            COL_PLAN_NAME: PLAN_NAME_KEEP
        }],
        keep_domains = KEEP_DOMAINS,
        plan_keep = KEEP_PLAN_NAMES,
        service_keep = KEEP_SERVICE_TYPES
    ) == [{
        **RESULT_DICT_DO_NOT_KEEP,
        COL_PLAN_NAME: PLAN_NAME_KEEP
    }]

def test_enabled_service_type_plan_name_true():
    assert _handle(
        usage_rows = [{
            **ROW_DICT,
            **SERVICE_PLAN_KEEP_ENABLED,
        }],
        keep_domains = KEEP_DOMAINS,
        plan_keep = KEEP_PLAN_NAMES,
        service_keep = KEEP_SERVICE_TYPES
    ) == [{
        **RESULT_DICT_KEEP,
        **SERVICE_PLAN_KEEP_ENABLED,
        **ROW_KEEP_PRODUCTION
    }]

def test_empty_service_type_false():
    assert _handle(
        usage_rows = [{
            **ROW_DICT,
            **SERVICE_PLAN_KEEP_ENABLED,
            COL_SERVICE_TYPE: '',
        }],
        keep_domains = KEEP_DOMAINS,
        plan_keep = KEEP_PLAN_NAMES,
        service_keep = KEEP_SERVICE_TYPES
    ) == [{
        **RESULT_DICT_DO_NOT_KEEP,
        **SERVICE_PLAN_KEEP_ENABLED,
        COL_SERVICE_TYPE: '',
    }]

def test_empty_plan_name_false():
    assert _handle(
        usage_rows = [{
            **ROW_DICT,
            **SERVICE_PLAN_KEEP_ENABLED,
            COL_PLAN_NAME: '',
        }],
        keep_domains = KEEP_DOMAINS,
        plan_keep = KEEP_PLAN_NAMES,
        service_keep = KEEP_SERVICE_TYPES
    ) == [{
        **RESULT_DICT_DO_NOT_KEEP,
        **SERVICE_PLAN_KEEP_ENABLED,
        COL_PLAN_NAME: '',
    }]

def test_unknown_service_type_error():
    with pytest.raises(ValueError, match=re.escape('service type "???" is not mapped')):
        _handle(
            usage_rows = [{
                **ROW_DICT,
                **SERVICE_PLAN_KEEP_ENABLED,
                COL_SERVICE_TYPE: '???',
            }],
            keep_domains = KEEP_DOMAINS,
            plan_keep = KEEP_PLAN_NAMES,
            service_keep = KEEP_SERVICE_TYPES
        )

def test_unknown_plan_name_error():
    with pytest.raises(ValueError, match=re.escape('plan name "???" is not mapped')):
        _handle(
            usage_rows = [{
                **ROW_DICT,
                **SERVICE_PLAN_KEEP_ENABLED,
                COL_PLAN_NAME: '???',
            }],
            keep_domains = KEEP_DOMAINS,
            plan_keep = KEEP_PLAN_NAMES,
            service_keep = KEEP_SERVICE_TYPES
        )

def test_not_keep_upstream_if_not_keep_down_stream():
    assert _handle(
        usage_rows = [{
            **ROW_DICT,
            **ROW_UPSTREAM,
        },{
            **ROW_DICT,
            **ROW_DOWNSTREAM,
        }],
        keep_domains = KEEP_DOMAINS,
        plan_keep = KEEP_PLAN_NAMES,
        service_keep = KEEP_SERVICE_TYPES
    ) == [{
        **RESULT_DICT_DO_NOT_KEEP,
        **ROW_UPSTREAM
    },{
        **RESULT_DICT_DO_NOT_KEEP,
        **ROW_DOWNSTREAM
    }]

def test_keep_upstream_if_keep_down_stream():
    assert _handle(
        usage_rows = [{
            **ROW_DICT,
            **ROW_UPSTREAM,
        },{
            **ROW_DICT,
            **ROW_DOWNSTREAM,
            **SERVICE_PLAN_KEEP_ENABLED
        }],
        keep_domains = KEEP_DOMAINS,
        plan_keep = KEEP_PLAN_NAMES,
        service_keep = KEEP_SERVICE_TYPES
    ) == [{
        **RESULT_DICT_KEEP,
        **ROW_UPSTREAM,
        **ROW_KEEP_DOWNSTREAM
    },{
        **RESULT_DICT_KEEP,
        **ROW_DOWNSTREAM,
        **SERVICE_PLAN_KEEP_ENABLED,
        **ROW_KEEP_PRODUCTION
    }]

def test_not_keep_upstream_if_keep_down_stream_on_other_env():
    assert _handle(
        usage_rows = [{
            **ROW_DICT,
            **ROW_UPSTREAM,
        },{
            **ROW_DICT,
            **ROW_DOWNSTREAM,
            **SERVICE_PLAN_KEEP_ENABLED,
            COL_ENVIRONMENT: 'other'
        }],
        keep_domains = KEEP_DOMAINS,
        plan_keep = KEEP_PLAN_NAMES,
        service_keep = KEEP_SERVICE_TYPES
    ) == [{
        **RESULT_DICT_DO_NOT_KEEP,
        **ROW_UPSTREAM
    },{
        **RESULT_DICT_KEEP,
        **ROW_DOWNSTREAM,
        **SERVICE_PLAN_KEEP_ENABLED,
        COL_ENVIRONMENT: 'other',
        **ROW_KEEP_PRODUCTION
    }]

def test_keep_downstream_if_keep_upstream_if_keep_downstream():
    assert _handle(
        usage_rows = [{
            **ROW_DICT,
            **ROW_UPSTREAM,
        },{
            **ROW_DICT,
            **ROW_DOWNSTREAM,
            **SERVICE_PLAN_KEEP_ENABLED
        },
        {
            **ROW_DICT,
            **ROW_DOWNSTREAM_2,
        }],
        keep_domains = KEEP_DOMAINS,
        plan_keep = KEEP_PLAN_NAMES,
        service_keep = KEEP_SERVICE_TYPES
    ) == [{
        **RESULT_DICT_KEEP,
        **ROW_UPSTREAM,
        **ROW_KEEP_DOWNSTREAM
    },{
        **RESULT_DICT_KEEP,
        **ROW_DOWNSTREAM,
        **SERVICE_PLAN_KEEP_ENABLED,
        **ROW_KEEP_PRODUCTION
    },{
        **RESULT_DICT_KEEP,
        **ROW_DOWNSTREAM_2,
        **ROW_KEEP_UPSTREAM
    }]

def test_parse_linked_domains():
    assert _parse_linked_domains(
        'woody-sample-apps,wm-location-import-test,https://staging.commcarehq.org/a/co-carecoordination-test/,https://staging.commcarehq.org/a/bha-auto-tests/',
        'test'
    ) == [
        ('test', 'woody-sample-apps'),
        ('test', 'wm-location-import-test'),
        ('staging', 'co-carecoordination-test'),
        ('staging', 'bha-auto-tests')
    ]
