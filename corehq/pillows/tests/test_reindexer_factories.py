from datetime import date

import pytest

from ..case import SqlCaseReindexerFactory
from ..xform import SqlFormReindexerFactory


@pytest.mark.parametrize("options, partial", [
    ({}, False),
    ({'domain': 'test'}, True),
    ({'limit_to_db': 'p1'}, True),
    ({'start_date': date(2026, 1, 1)}, True),
    ({'end_date': date(2026, 1, 1)}, True),
])
def test_sql_case_reindexer_is_partial(options, partial):
    reindexer = SqlCaseReindexerFactory(**options).build()
    assert reindexer.partial is partial


@pytest.mark.parametrize("options, partial", [
    ({}, False),
    ({'domain': 'test'}, True),
    ({'limit_to_db': 'p1'}, True),
])
def test_sql_form_reindexer_is_partial(options, partial):
    reindexer = SqlFormReindexerFactory(**options).build()
    assert reindexer.partial is partial
