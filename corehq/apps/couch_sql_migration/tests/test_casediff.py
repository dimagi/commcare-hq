from __future__ import absolute_import
from __future__ import unicode_literals

import attr
import gevent
import six
from django.test import SimpleTestCase
from mock import patch

from ..casediff import CaseDiffQueue
from ..statedb import delete_state_db, init_state_db


@patch.object(gevent.get_hub(), "SYSTEM_ERROR", BaseException)
class TestCaseDiffQueue(SimpleTestCase):

    def setUp(self):
        def make_get_cases():
            return lambda case_ids: [self.cases[x] for x in case_ids]

        def diff_cases(cases):
            for case in six.itervalues(cases):
                case_id = case["_id"]
                if case_id in diffed:
                    diffed[case_id] += 1
                else:
                    diffed[case_id] = 1

        self.close_context = _test_context(self,
            get_cases=patch(
                "corehq.form_processor.backends.couch.dbaccessors."
                "CaseAccessorCouch.get_cases",
                new_callable=make_get_cases,
            ),
            statedb=init_state_db("test"),
        )

        self.cases = {}
        self.diffed = diffed = {}
        self.queue = CaseDiffQueue(self.statedb, diff_cases)

    def tearDown(self):
        self.close_context()
        delete_state_db("test")

    def add_case(self, case_id, xform_ids=None):
        if isinstance(xform_ids, six.text_type):
            xform_ids = xform_ids.split()
        self.cases[case_id] = FakeCase(case_id, xform_ids or [])

    def test_case_diff(self):
        self.add_case("cx", "fx")
        with self.queue as queue:
            queue.update({"cx"}, "fx")
        self.assertEqual(self.diffed, {"cx": 1})


@attr.s
class FakeCase(object):

    _id = attr.ib()
    xform_ids = attr.ib(factory=list)
    actions = attr.ib(factory=list)

    @property
    def case_id(self):
        return self._id

    def to_json(self):
        return {f.name: getattr(self, f.name) for f in attr.fields(type(self))}


def _test_context(test, **contexts):
    def close():
        for context in six.itervalues(contexts):
            context.__exit__(None, None, None)

    for name, context in six.iteritems(contexts):
        value = context.__enter__()
        setattr(test, name, value)
    return close
