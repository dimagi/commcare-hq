from datetime import timedelta

from gevent.pool import Pool
from mock import patch

from corehq.form_processor.utils.general import (
    clear_local_domain_sql_backend_override,
)

from .test_migration import BaseMigrationTestCase, Diff, make_test_form
from ..management.commands import couch_sql_diff as mod
from ..statedb import open_state_db


class TestCouchSqlDiff(BaseMigrationTestCase):

    @classmethod
    def setUpClass(cls):
        cls.pool_mock = patch.object(mod, "Pool", MockPool)
        cls.pool_mock.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.pool_mock.stop()

    def test_diff(self):
        self.submit_form(make_test_form("form-1", case_id="case-1"))
        self._do_migration(case_diff="none")
        clear_local_domain_sql_backend_override(self.domain_name)
        case = self._get_case("case-1")
        case.age = '35'
        case.save()
        self.do_case_diffs()
        self._compare_diffs([
            ('CommCareCase', Diff('diff', ['age'], old='35', new='27')),
        ])

    def test_diff_specific_case(self):
        self.submit_form(make_test_form("form-1", case_id="case-1"))
        self._do_migration(case_diff="none")
        clear_local_domain_sql_backend_override(self.domain_name)
        case = self._get_case("case-1")
        case.age = '35'
        case.save()
        self.do_case_diffs(cases="case-1")
        self._compare_diffs([
            ('CommCareCase', Diff('diff', ['age'], old='35', new='27')),
        ])

    def test_pending_diff(self):
        def diff_none(case_ids):
            return mod.DiffData([])
        self.submit_form(make_test_form("form-1", case_id="case-1"))
        self._do_migration(case_diff='none')
        clear_local_domain_sql_backend_override(self.domain_name)
        case = self._get_case("case-1")
        case.age = '35'
        case.save()
        with patch.object(mod, "diff_cases", diff_none):
            result = self.do_case_diffs()
        self.assertEqual(result, mod.PENDING_WARNING)
        self.do_case_diffs(cases="pending")
        self._compare_diffs([
            ('CommCareCase', Diff('diff', ['age'], old='35', new='27')),
        ])

    def test_live_diff(self):
        # do not diff case modified since most recent case created in SQL
        self.submit_form(make_test_form("form-1", case_id="case-1"), timedelta(minutes=-90))
        self.submit_form(make_test_form("form-2", case_id="case-1", age=35))
        self._do_migration(live=True, chunk_size=1, case_diff="none")
        self.assert_backend("sql")
        case = self._get_case("case-1")
        self.assertEqual(case.dynamic_case_properties()["age"], '27')
        self.do_case_diffs(live=True)
        self._compare_diffs([])

    def test_failed_diff(self):
        self.submit_form(make_test_form("form-1", case_id="case-1"))
        self._do_migration(case_diff="none")
        with patch.object(mod, "diff_case") as mock:
            mock.side_effect = Exception("fail!")
            self.do_case_diffs()
        self._compare_diffs([])
        db = open_state_db(self.domain_name, self.state_dir)
        self.assertEqual(list(db.iter_undiffed_case_ids()), ["case-1"])

    def test_reconcile_transaction_order(self):
        from ..rebuildcase import SortTransactionsRebuild
        form1 = make_test_form("form-1", age="33", date="2016-08-04T18:25:56.656Z")
        form2 = make_test_form("form-2", age="32", date="2015-08-04T18:25:56.656Z")
        self.submit_form(form1)
        self.submit_form(form2)
        self.assertEqual(self._get_case("test-case").age, "33")
        self._do_migration(case_diff="local")
        self._compare_diffs([
            ('CommCareCase', Diff('diff', ['age'], old='33', new='32')),
        ])
        clear_local_domain_sql_backend_override(self.domain_name)
        self.do_case_diffs()
        sql_case = self._get_case("test-case")
        self.assertEqual(sql_case.dynamic_case_properties()["age"], "33")
        self._compare_diffs([], ignore_fail=True)
        details = sql_case.transactions[-1].details
        self.assertEqual(details["reason"], SortTransactionsRebuild._REASON)
        server_dates = details["original_server_dates"]
        self.assertEqual(len(server_dates), 1, server_dates)

    def do_case_diffs(self, live=False, cases=None):
        migrator = mod.get_migrator(self.domain_name, self.state_dir, live)
        return mod.do_case_diffs(migrator, cases)


def MockPool(initializer=lambda: None, initargs=(), maxtasksperchild=None):
    initializer(*initargs)
    return Pool()
