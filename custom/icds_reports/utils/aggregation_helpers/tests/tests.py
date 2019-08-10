# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import difflib
import inspect
import json
import os
from collections import OrderedDict
from datetime import datetime

import attr
from django.core.serializers.json import DjangoJSONEncoder
from django.test import SimpleTestCase
from django.utils.functional import cached_property
from freezegun import freeze_time
from mock import patch

from custom.icds_reports.utils.aggregation_helpers.helpers import HELPERS
from io import open

BASE_PATH = os.path.join(os.path.dirname(__file__), 'sql_output')


@attr.s
class SqlOutput(object):
    helper_key = attr.ib()
    monolith_sql = attr.ib()
    distributed_sql = attr.ib()

    @property
    def monolith_path(self):
        return os.path.join(BASE_PATH, '{}.monolith.txt'.format(self.helper_key))

    @property
    def distributed_path(self):
        return os.path.join(BASE_PATH, '{}.distributed.txt'.format(self.helper_key))

    def write(self):
        with open(self.monolith_path, 'w') as f_monolith:
            f_monolith.write(self.monolith_sql)
        with open(self.distributed_path, 'w') as f_distributed:
            f_distributed.write(self.distributed_sql)

    @cached_property
    def saved_monolith_sql(self):
        with open(self.monolith_path, 'r') as f_monolith:
            return f_monolith.read()

    @cached_property
    def saved_distributed_sql(self):
        with open(self.distributed_path, 'r') as f_distributed:
            return f_distributed.read()

    def get_diffs(self):
        monolith_diff, distributed_diff = None, None
        if self.monolith_sql != self.saved_monolith_sql:
            monolith_diff = get_diff(self.saved_monolith_sql, self.monolith_sql)
        if self.distributed_sql != self.saved_distributed_sql:
            distributed_diff = get_diff(self.saved_distributed_sql, self.distributed_sql)
        return monolith_diff, distributed_diff


class TestQueryDiffs(SimpleTestCase):
    def test_agg_sql_diff(self):
        outputs = get_agg_helper_outputs()
        diff_output = []
        for output in outputs:
            monolith_diff, distributed_diff = output.get_diffs()
            if monolith_diff or distributed_diff:
                diff_output.append("\n{0} Diffs detected for agg helper '{1}' {0}".format(
                    '-' * 20, output.helper_key
                ))
                if monolith_diff:
                    diff_output.append("\nMONOLITH DIFF\n=================")
                    diff_output.append(monolith_diff)
                if distributed_diff:
                    diff_output.append("\nDISTRIBUTED DIFF\n=================")
                    diff_output.append(distributed_diff)
        if diff_output:
            raise AssertionError('{}\n\n{}'.format(
                '\n'.join(diff_output),
                inspect.cleandoc("""

                To fix these diffs:
                    1. Make sure you have applied changes to both the "monolith" and the "distributed"
                       helper classes.
                    2. Run "python manage.py update_icds_aggregation_output" and commit the changes.

                """)
            ))


def get_diff(saved, generated):
    diff = difflib.unified_diff(
        saved.splitlines(), generated.splitlines(),
        fromfile='master', tofile='branch'
    )
    return '\n'.join(diff)


class MockCursor(object):
    def __init__(self):
        self.output = []

    def execute(self, query, params=None):
        params = json.dumps(OrderedDict(sorted(params.items())), cls=DjangoJSONEncoder) if params else '{}'
        self.output.append('{}\n{}'.format(query, params))

    def compile_output(self):
        return '\n'.join(self.output)


ARGS = {
    'month': datetime(2019, 1, 1),
    'date': datetime(2019, 1, 1),
    'state_id': 'st1',
    'state_ids': ['st1', 'st2'],
    'last_sync': datetime(2019, 1, 5),
}


def _get_helper(helper_cls):
    if not helper_cls:
        return

    args = inspect.getargspec(helper_cls.__init__)
    arg_vals = [
        ARGS[arg] for arg in args.args[1:]  # skip 'self'
    ]
    return helper_cls(*arg_vals)


def _get_helper_sql(helper_cls):
    helper = _get_helper(helper_cls)
    mock_cursor = MockCursor()
    monolith_patch = patch(
        'custom.icds_reports.utils.aggregation_helpers.monolith.awc_location._get_all_locations_for_domain',
        return_value=[])
    distributed_patch = patch(
        'custom.icds_reports.utils.aggregation_helpers.distributed.awc_location._get_all_locations_for_domain',
        return_value=[])
    monolith_patch.start()
    distributed_patch.start()

    if hasattr(helper, 'aggregate'):
        try:
            helper.aggregate(mock_cursor)
        except AttributeError as e:
            # For locations we use psycopg2's cursor to do a CSV copy to
            if "'MockCursor' object has no attribute 'cursor'" not in str(e):
                raise
    elif hasattr(helper, 'query'):
        mock_cursor.execute(helper.query())
    elif helper is not None:
        raise AssertionError("Unexepcted helper type: {}".format(helper_cls))

    monolith_patch.stop()
    distributed_patch.stop()

    return mock_cursor.compile_output()


def _get_helper_weekly_sql(helper_cls):
    helper = _get_helper(helper_cls)
    mock_cursor = MockCursor()

    if hasattr(helper, 'weekly_aggregate'):
        helper.aggregate(mock_cursor)

    return mock_cursor.compile_output()


def get_agg_helper_outputs():
    with freeze_time(datetime(2019, 1, 11)):
        for pair in HELPERS:
            yield SqlOutput(
                pair.monolith.helper_key,
                _get_helper_sql(pair.monolith),
                _get_helper_sql(pair.distributed)
            )

            weekly_sql_monolith = _get_helper_weekly_sql(pair.monolith)
            weekly_sql_disributed = _get_helper_weekly_sql(pair.distributed)
            if weekly_sql_monolith or weekly_sql_disributed:
                yield SqlOutput(
                    '{}_weekly'.format(pair.monolith.helper_key),
                    weekly_sql_monolith,
                    weekly_sql_disributed
                )
