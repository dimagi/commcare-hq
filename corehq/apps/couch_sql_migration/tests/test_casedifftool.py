import json
from contextlib import contextmanager
from datetime import datetime, timedelta
from xml.sax.saxutils import unescape

from mock import patch

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseIndex

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.tzmigration.timezonemigration import MISSING
from corehq.form_processor.backends.couch.dbaccessors import CaseAccessorCouch
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.models import CommCareCaseIndexSQL
from corehq.form_processor.utils.general import (
    clear_local_domain_sql_backend_override,
)
from corehq.util.dates import iso_string_to_datetime
from corehq.util.test_utils import capture_log_output

from .test_migration import BaseMigrationTestCase, Diff, IGNORE, make_test_form
from .. import casediff
from .. import casedifftool as mod
from ..diffrule import ANY
from ..statedb import open_state_db


class TestCouchSqlDiff(BaseMigrationTestCase):

    def test_diff(self):
        self.submit_form(make_test_form("form-1", case_id="case-1"))
        self.do_migration(case_diff="none")
        clear_local_domain_sql_backend_override(self.domain_name)
        with self.augmented_couch_case("case-1") as case:
            case.age = '35'
            case.save()
            self.do_case_diffs()
        self.compare_diffs([
            Diff('case-1', 'diff', ['age'], old='35', new='27'),
        ])
        self.do_migration(forms="missing", case_diff="patch")

    def test_diff_specific_case(self):
        self.submit_form(make_test_form("form-1", case_id="case-1"))
        self.do_migration(case_diff="none")
        clear_local_domain_sql_backend_override(self.domain_name)
        with self.augmented_couch_case("case-1") as case:
            case.age = '35'
            case.save()
            self.do_case_diffs(cases="case-1")
        self.compare_diffs([
            Diff('case-1', 'diff', ['age'], old='35', new='27'),
        ])

    def test_pending_diff(self):
        def diff_none(case_ids, log_cases=None):
            return casediff.DiffData([])
        self.submit_form(make_test_form("form-1", case_id="case-1"))
        self.do_migration(case_diff='none')
        clear_local_domain_sql_backend_override(self.domain_name)
        with self.augmented_couch_case("case-1") as case:
            case.age = '35'
            case.save()
            with patch("corehq.apps.couch_sql_migration.casedifftool.diff_cases", diff_none):
                result = self.do_case_diffs()
            self.assertEqual(result, mod.PENDING_WARNING)
            self.do_case_diffs(cases="pending")
        self.compare_diffs([
            Diff('case-1', 'diff', ['age'], old='35', new='27'),
        ])

    def test_live_diff(self):
        # do not diff case modified since most recent case created in SQL
        self.submit_form(make_test_form("form-1", case_id="case-1"), timedelta(minutes=-90))
        self.submit_form(make_test_form("form-2", case_id="case-1", age=35))
        self.do_migration(live=True, chunk_size=1, case_diff="none")
        self.assert_backend("sql")
        case = self._get_case("case-1")
        self.assertEqual(case.dynamic_case_properties()["age"], '27')
        self.do_case_diffs()
        self.compare_diffs(ignore_fail=True)

    def test_failed_diff(self):
        self.pool_mock.stop()
        self.addCleanup(self.pool_mock.start)
        self.submit_form(make_test_form("form-1", case_id="case-1"))
        self.do_migration(case_diff="none")
        # patch init_worker to make subprocesses use the same database
        # connections as this process (which is operating in a transaction)
        init_worker_path = "corehq.apps.couch_sql_migration.casedifftool.init_worker"
        with patch(init_worker_path, mod.global_diff_state), \
                patch("corehq.apps.couch_sql_migration.casediff.diff_case") as mock, \
                capture_log_output("corehq.apps.couch_sql_migration.parallel") as log:
            mock.side_effect = Exception("diff failed!")
            self.do_case_diffs()
        logs = log.get_output()
        self.assertIn("error processing item in worker", logs)
        self.assertIn("Exception: diff failed!", logs)
        self.compare_diffs()
        db = open_state_db(self.domain_name, self.state_dir)
        self.assertEqual(list(db.iter_undiffed_case_ids()), ["case-1"])

    def test_reconcile_transaction_order(self):
        from ..rebuildcase import SortTransactionsRebuild
        form1 = make_test_form("form-1", age="33", date="2016-08-04T18:25:56.656Z")
        form2 = make_test_form("form-2", age="32", date="2015-08-04T18:25:56.656Z")
        self.submit_form(form1)
        self.submit_form(form2)
        self.assertEqual(self._get_case("test-case").age, "33")
        with self.diff_without_rebuild():
            self.do_migration()
        self.compare_diffs([
            Diff('test-case', 'diff', ['age'], old='33', new='32'),
        ])
        clear_local_domain_sql_backend_override(self.domain_name)
        self.do_case_diffs(cases="with-diffs")
        sql_case = self._get_case("test-case")
        self.assertEqual(sql_case.dynamic_case_properties()["age"], "33")
        self.compare_diffs()
        details = sql_case.transactions[-1].details
        self.assertEqual(details["reason"], SortTransactionsRebuild._REASON)
        server_dates = details["original_server_dates"]
        self.assertEqual(len(server_dates), 1, server_dates)

    def test_couch_with_missing_forms(self):
        form1 = make_test_form("form-1", age="33", date="2016-08-04T18:25:56.656Z")
        form2 = make_test_form("form-2", age="32", date="2015-08-04T18:25:56.656Z")
        self.submit_form(THING_FORM)
        self.submit_form(form1)
        self.submit_form(form2)
        case = self._get_case("test-case")
        self.assertEqual(case.age, "33")
        self.assertEqual(case.thing, "1")
        del case.thing
        case.actions = [a for a in case.actions if a.form_id != "thing-form"]
        case.save()
        with self.assertRaises(AttributeError):
            self._get_case("test-case").thing
        with self.diff_without_rebuild():
            self.do_migration()
        self.compare_diffs([
            Diff('test-case', 'diff', ['age'], old='33', new='32'),
            Diff('test-case', 'missing', ['thing'], old=MISSING, new='1'),
        ])
        clear_local_domain_sql_backend_override(self.domain_name)
        self.do_case_diffs(cases="with-diffs")
        sql_case = self._get_case("test-case")
        self.assertEqual(sql_case.dynamic_case_properties()["age"], "33")
        self.compare_diffs(changes=[
            Diff('test-case', 'missing', ['thing'], old=MISSING, new='1', reason='rebuild case'),
        ])
        self.do_migration(patch=True, diffs=[])

    def test_couch_missing_create_case(self):
        with self.skip_case_and_ledger_updates("thing-form"):
            self.submit_form(THING_FORM)
        self.submit_form(UPDATE_FORM)
        case = self._get_case("test-case")
        # simulate null properties seen in the wild
        object.__setattr__(case, "name", None)
        object.__setattr__(case, "type", None)
        case.save()
        with self.diff_without_rebuild():
            self.do_migration()
        self.compare_diffs([
            Diff('test-case', 'missing', ['thing'], old=MISSING, new='1'),
            Diff('test-case', 'set_mismatch', ['xform_ids', '[*]'], old='', new='thing-form'),
            Diff('test-case', 'type', ['name'], old=None, new='Thing'),
            Diff('test-case', 'type', ['type'], old=None, new='testing'),
        ])
        self.do_migration(patch=True, diffs=[])
        case = self._get_case("test-case")
        self.assertEqual(case.name, "")
        self.assertEqual(case.type, "")
        self.assertEqual(case.dynamic_case_properties()["thing"], "")
        self.assertEqual(case.xform_ids, ['thing-form', 'update-form', ANY])

    def test_case_with_deleted_form(self):
        # form state=normal / deleted -> missing case
        one = self.submit_form(make_test_form("one", age=27))
        FormAccessors(self.domain_name).soft_delete_forms(
            [one.form_id], datetime.utcnow(), 'test-deletion')
        self.do_migration()
        self.compare_diffs(changes=[
            Diff('test-case', 'missing', ['*'], old='*', new=MISSING, reason="deleted forms"),
        ])

    def test_diff_case_with_wrong_domain(self):
        wrong_domain = create_domain("wrong")
        self.addCleanup(wrong_domain.delete)
        self.submit_form(make_test_form("form-1"), domain="wrong")
        self.do_migration(case_diff="none", domain="wrong")
        self.do_migration(case_diff="none")
        clear_local_domain_sql_backend_override(self.domain_name)
        with capture_log_output("corehq.apps.couch_sql_migration") as log, \
                self.augmented_couch_case("test-case") as case:
            # modify case so it would have a diff (if it were diffed)
            case.age = '35'
            case.save()
            # try to diff case in wrong domain
            self.do_case_diffs(cases="test-case")
        self.compare_diffs([
            Diff('test-case', 'diff', ['domain'], old='wrong', new=self.domain_name),
        ])
        logs = log.get_output()
        self.assertIn("couch case test-case has wrong domain: wrong", logs)

    def test_ledger_dup_transaction_diff(self):
        product_id = self.create_form_with_duplicate_stock_transaction()
        self.do_migration(case_diff='none')
        self.compare_diffs(ignore_fail=True)
        clear_local_domain_sql_backend_override(self.domain_name)
        self.do_case_diffs()
        self.compare_diffs(changes=[Diff(
            f"test-case/things/{product_id}",
            reason="duplicate stock transaction",
            type="diff",
            path=["balance"],
            old=2,
            new=1,
            kind="stock state",
        )])

    def test_patch_known_properties(self):
        self.submit_form(make_test_form("form-1", case_id="case-1"))
        self.do_migration(case_diff="none")
        clear_local_domain_sql_backend_override(self.domain_name)
        open_date = datetime(2010, 9, 8)
        with self.augmented_couch_case("case-1") as case:
            case.name = "Zena"
            case.type = "old-type"
            case.user_id = "old-user"
            case.owner_id = "old-owner"
            case.opened_on = open_date
            case.save()
            self.do_case_diffs()
        self.compare_diffs([
            Diff('case-1', 'diff', ['name'], old='Zena', new='Xeenax'),
            Diff('case-1', 'diff', ['owner_id'], old='old-owner', new='3fae4ea4af440efaa53441b5'),
            Diff('case-1', 'diff', ['type'], old='old-type', new='testing'),
            Diff('case-1', 'diff', ['user_id'], old='old-user', new='3fae4ea4af440efaa53441b5'),
        ])
        self.do_migration(forms="missing", case_diff="patch")
        self.assertEqual(self._get_case("case-1").opened_on, open_date)

    def test_unpatchable_properties(self):
        date1 = "2018-07-13T11:20:11.381000Z"
        self.submit_form(make_test_form("form-1", case_id="case-1"))
        case = self._get_case("case-1")
        user = case.user_id
        case.closed = True
        case.closed_by = "someone"
        case.closed_on = iso_string_to_datetime(date1)
        case.external_id = "ext"
        case.name = "Zena"
        case.opened_by = "someone"
        case.server_modified_on = iso_string_to_datetime(date1)
        case.user_id = "person"
        case.save()
        self.do_migration(diffs=[
            Diff('case-1', 'diff', ['closed'], old=True, new=False),
            Diff('case-1', 'diff', ['closed_by'], old='someone', new=''),
            Diff('case-1', 'diff', ['external_id'], old='ext', new=''),
            Diff('case-1', 'diff', ['name'], old='Zena', new='Xeenax'),
            Diff('case-1', 'diff', ['opened_by'], old='someone', new=user),
            Diff('case-1', 'diff', ['user_id'], old='person', new=user),
            Diff('case-1', 'type', ['closed_on'], old=date1, new=None),
        ])
        self.do_migration(patch=True, diffs=[])
        close2 = iso_string_to_datetime("2015-08-04T18:25:56.656Z")
        case = self._get_case("case-1")
        self.assertEqual(case.closed, True)         # patched
        self.assertEqual(case.closed_by, "person")  # unpatched
        self.assertEqual(case.closed_on, close2)    # unpatched
        self.assertEqual(case.external_id, 'ext')   # patched, not sure how/why
        self.assertEqual(case.name, "Zena")         # patched
        self.assertEqual(case.opened_by, user)      # unpatched
        self.assertEqual(case.user_id, "person")    # patched
        self.assertNotEqual(case.server_modified_on,
                            iso_string_to_datetime(date1))  # unpatched
        form = self._get_form(case.xform_ids[-1])
        diffs = json.loads(unescape(form.form_data["diff"]))
        self.assertEqual(diffs, {
            "case_id": "case-1",
            "diffs": [
                {"path": ["closed"], "old": True, "new": False, "patch": True},
                {"path": ["closed_by"], "old": "someone", "new": "", "patch": False},
                {"path": ["closed_on"], "old": date1, "new": None, "patch": False},
                {"path": ["external_id"], "old": "ext", "new": "", "patch": False},
                {"path": ["name"], "old": "Zena", "new": "Xeenax", "patch": True},
                {"path": ["opened_by"], "old": "someone", "new": user, "patch": False},
                {"path": ["user_id"], "old": "person", "new": user, "patch": True},
            ],
        })

    def test_patch_closed_case(self):
        from casexml.apps.case.cleanup import close_case
        self.submit_form(make_test_form("form-1", case_id="case-1"))
        close_case("case-1", self.domain_name, "system", "test")
        self.do_migration(case_diff="none")
        clear_local_domain_sql_backend_override(self.domain_name)
        with self.augmented_couch_case("case-1") as case:
            case.name = "Zena"
            case.save()
            self.do_case_diffs()
        self.compare_diffs([
            Diff('case-1', 'diff', ['name'], old='Zena', new='Xeenax'),
        ])
        self.do_migration(forms="missing", case_diff="patch")
        self.assertEqual(self._get_case("case-1").closed, True)
        self.assert_patched_cases(["case-1"])

    def test_patch_case_needing_sql_rebuild(self):
        with self.skip_case_and_ledger_updates("form-1"):
            self.submit_form(make_test_form("form-1", age=30))
        self.submit_form(make_test_form("form-2"))
        with self.diff_without_rebuild():
            self.do_migration()
        with patch.object(mod.CaseDiffTool, "diff_cases"):
            self.do_case_patch()
        self.compare_diffs([
            Diff('test-case', 'set_mismatch', ['xform_ids', '[*]'], old='', new='form-1'),
        ])
        case = self._get_case("test-case")
        case.case_json["age"] = "30"  # diff -> reubild SQL case
        case.save()
        self.do_case_diffs("pending")
        self.compare_diffs([])
        self.assert_patched_cases(["test-case"])

    def test_cannot_patch_case_missing_in_couch(self):
        self.submit_form(make_test_form("form-1", case_id="case-1"))
        self.do_migration(case_diff="none")
        CommCareCase.get_db().delete_doc("case-1")
        self.do_migration(forms="missing", case_diff="patch", diffs=[
            Diff('case-1', 'missing', ['*'], old=MISSING, new='present'),
        ])
        self.assert_patched_cases()

    def test_convert_error_form_for_case_missing_in_couch(self):
        def find_forms(case_id):
            return ["form-1"]
        self.submit_form(make_test_form("form-1", case_id="case-1"))
        self.do_migration(case_diff="none")
        CommCareCase.get_db().delete_doc("case-1")
        clear_local_domain_sql_backend_override(self.domain_name)
        form = self._get_form("form-1")
        form.problem = "something went wrong"
        form.save()
        self.do_case_diffs("pending")
        self.compare_diffs([
            Diff('case-1', 'missing', ['*'], old=MISSING, new='present'),
        ])
        with patch.object(casediff, "find_form_ids_updating_case", find_forms):
            self.do_migration(forms="missing", diffs=[])

    def test_patch_case_closed_in_couch_not_sql(self):
        self.submit_form(make_test_form("form-1", case_id="case-1"))
        self.do_migration(case_diff="none")
        with self.augmented_couch_case("case-1") as case:
            case.closed = True
            case.closed_by = "system"
            case.closed_on = datetime(2010, 9, 8, 7, 6, 5)
            case.user_id = "system"
            case.save()
            self.do_case_diffs()
        self.compare_diffs([
            Diff('case-1', 'diff', ['closed'], old=True, new=False),
            Diff('case-1', 'diff', ['user_id'], old='system', new='3fae4ea4af440efaa53441b5'),
            Diff('case-1', 'type', ['closed_by'], old='system', new=None),
            Diff('case-1', 'type', ['closed_on'], old='2010-09-08T07:06:05.000000Z', new=None),
        ])
        self.do_case_patch()
        self.compare_diffs()
        self.assert_patched_cases(["case-1"])

    def test_patch_case_index(self):
        self.submit_form(make_test_form("form-1", case_id="case-1"))
        self.do_migration(case_diff="none")
        index = {
            "doc_type": "CommCareCaseIndex",
            "identifier": "parent",
            "referenced_type": "household",
            "referenced_id": "a53346d5",
            "relationship": "child",
        }
        with self.augmented_couch_case("case-1") as case:
            case.indices = [CommCareCaseIndex.wrap(index)]
            case.save()
            self.do_case_diffs()
        self.compare_diffs([
            Diff('case-1', 'missing', ['indices', '[*]'], old=index, new=MISSING),
        ])
        self.do_case_patch()
        self.compare_diffs()
        self.assert_patched_cases(["case-1"])

    def test_patch_missing_case_index(self):
        self.submit_form(make_test_form("form-1", case_id="case-1"))
        self.do_migration(case_diff="none")
        CommCareCaseIndexSQL(
            domain=self.domain_name,
            case_id="case-1",
            identifier="parent",
            referenced_id="a53346d5",
            referenced_type="household",
            relationship_id=CommCareCaseIndexSQL.CHILD,
        ).save()
        with self.diff_without_rebuild():
            self.do_case_diffs()
        index = {
            "case_id": "case-1",
            "identifier": "parent",
            "referenced_id": "a53346d5",
            "referenced_type": "household",
            "relationship": "child",
        }
        self.compare_diffs([
            Diff('case-1', 'missing', ['indices', '[*]'], old=MISSING, new=index),
        ])
        with self.diff_without_rebuild():
            self.do_case_patch()
        self.compare_diffs()
        self.assert_patched_cases(["case-1"])

    def create_form_with_duplicate_stock_transaction(self):
        from corehq.apps.commtrack.helpers import make_product
        from corehq.apps.commtrack.processing import process_stock
        thing1 = make_product(self.domain_name, 'thing-1', 'thing-1')
        self.submit_form(LEDGER_FORM.replace("thing-1", thing1._id))
        stock_result = process_stock([self._get_form("ledger-form")])
        stock_result.populate_models()
        for model in stock_result.models_to_save:
            model.save()
        return thing1._id

    def do_migration(self, *args, **kw):
        if kw.get("case_diff") != "patch":
            kw.setdefault("diffs", IGNORE)
        return super().do_migration(*args, **kw)

    def do_case_diffs(self, cases=None, stop=False):
        self.migration_success = True  # clear migration failure on diff cases
        migrator = mod.get_migrator(self.domain_name, self.state_dir)
        return mod.do_case_diffs(migrator, cases, stop=stop, batch_size=100)

    def do_case_patch(self, cases=None, stop=False):
        self.migration_success = True  # clear migration failure on diff cases
        migrator = mod.get_migrator(self.domain_name, self.state_dir)
        return mod.do_case_patch(migrator, cases, stop=stop, batch_size=100)

    @contextmanager
    def augmented_couch_case(self, case_id):
        case = CaseAccessorCouch.get_case(case_id)
        with self.diff_without_rebuild():
            yield case

    def assert_patched_cases(self, case_ids=None):
        statedb = open_state_db(self.domain_name, self.state_dir)
        self.assertEqual(list(statedb.iter_patched_case_ids()), case_ids or [])
        self.assertFalse(list(statedb.iter_undiffed_case_ids()))


THING_FORM = """
<?xml version="1.0" ?>
<data
    name="Thing"
    uiVersion="1"
    version="11"
    xmlns="http://openrosa.org/formdesigner/thing-form"
    xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
>
    <thing>1</thing>
    <n0:case
        case_id="test-case"
        date_modified="2014-08-04T18:25:56.656Z"
        user_id="a362027f228d"
        xmlns:n0="http://commcarehq.org/case/transaction/v2"
    >
        <n0:create>
            <n0:case_name>Thing</n0:case_name>
            <n0:owner_id>a362027f228d</n0:owner_id>
            <n0:case_type>testing</n0:case_type>
        </n0:create>
        <n0:update>
            <n0:thing>1</n0:thing>
        </n0:update>
    </n0:case>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>cloudcare</n1:deviceID>
        <n1:timeStart>2014-07-13T11:20:11.381Z</n1:timeStart>
        <n1:timeEnd>2014-08-04T18:25:56.656Z</n1:timeEnd>
        <n1:username>thing</n1:username>
        <n1:userID>a362027f228d</n1:userID>
        <n1:instanceID>thing-form</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms">2.0</n2:appVersion>
    </n1:meta>
</data>
""".strip()


UPDATE_FORM = """
<?xml version="1.0" ?>
<data
    name="Update"
    uiVersion="1"
    version="11"
    xmlns="http://openrosa.org/formdesigner/update-form"
    xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
>
    <age>27</age>
    <n0:case
        case_id="test-case"
        date_modified="2015-08-04T18:25:56.656Z"
        user_id="3fae4ea4af440efaa53441b5"
        xmlns:n0="http://commcarehq.org/case/transaction/v2"
    >
        <n0:update>
            <n0:age>27</n0:age>
        </n0:update>
    </n0:case>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>cloudcare</n1:deviceID>
        <n1:timeStart>2015-07-13T11:20:11.381Z</n1:timeStart>
        <n1:timeEnd>2015-08-04T18:25:56.656Z</n1:timeEnd>
        <n1:username>jeremy</n1:username>
        <n1:userID>3fae4ea4af440efaa53441b5</n1:userID>
        <n1:instanceID>update-form</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms">2.0</n2:appVersion>
    </n1:meta>
</data>
""".strip()


LEDGER_FORM = """
<?xml version="1.0" ?>
<data
    name="Ledger"
    uiVersion="1"
    version="11"
    xmlns="http://openrosa.org/formdesigner/ledger-form"
    xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
>
    <thing>1</thing>
    <n2:transfer
        date="2014-08-04"
        dest="test-case"
        section-id="things"
        type="write_things_to_ledger"
        xmlns:n2="http://commcarehq.org/ledger/v1"
    >
        <n2:entry id="thing-1" quantity="1"/>
    </n2:transfer>
    <n0:case
        case_id="test-case"
        date_modified="2014-08-04T18:25:56.656Z"
        user_id="a362027f228d"
        xmlns:n0="http://commcarehq.org/case/transaction/v2"
    >
        <n0:create>
            <n0:case_name>Ledger</n0:case_name>
            <n0:owner_id>a362027f228d</n0:owner_id>
            <n0:case_type>testing</n0:case_type>
        </n0:create>
        <n0:update>
            <n0:thing>1</n0:thing>
        </n0:update>
    </n0:case>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>cloudcare</n1:deviceID>
        <n1:timeStart>2014-07-13T11:20:11.381Z</n1:timeStart>
        <n1:timeEnd>2014-08-04T18:25:56.656Z</n1:timeEnd>
        <n1:username>thing</n1:username>
        <n1:userID>a362027f228d</n1:userID>
        <n1:instanceID>ledger-form</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms">2.0</n2:appVersion>
    </n1:meta>
</data>
""".strip()
