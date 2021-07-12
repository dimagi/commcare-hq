import json
from unittest.mock import patch
from xml.sax.saxutils import unescape

import attr
from testil import eq

from corehq.apps.tzmigration.timezonemigration import FormJsonDiff as Diff, MISSING

from .. import casediff
from .. import casepatch as mod


def test_patch_opened_by():
    diffs = [Diff("diff", ["opened_by"], "old", "new")]
    case = mod.PatchCase(FakeCase(), diffs, [])
    check_diff_block(case, diffs)


def test_patch_closed_by():
    diffs = [Diff("diff", ["closed_by"], "old", "new")]
    case = mod.PatchCase(FakeCase(), diffs, [])
    check_diff_block(case, diffs)


def test_patch_modified_by():
    diffs = [Diff("diff", ["modified_by"], "old", "new")]
    case = mod.PatchCase(FakeCase(), diffs, [])
    check_diff_block(case, diffs)


def test_patch_opened_by_with_xform_ids():
    diffs = [
        Diff("diff", ["opened_by"], "old", "new"),
        Diff("set_mismatch", ["xform_ids", "[*]"], "old", "new"),
    ]
    case = mod.PatchCase(FakeCase(), diffs, [])
    check_diff_block(case, diffs)


def test_can_patch_opened_by_with_user_id():
    diffs = [
        Diff("diff", ["opened_by"], "old", "new"),
        Diff("diff", ["user_id"], "old", "new"),
    ]
    case = mod.PatchCase(FakeCase(), diffs, [])
    eq(case.dynamic_case_properties(), {})
    check_diff_block(case, diffs)


def test_patch_missing_case_property():
    diffs = [Diff("diff", ["gone"], MISSING, "new")]
    case = mod.PatchCase(FakeCase(), diffs, [])
    eq(case.dynamic_case_properties(), {"gone": ""})
    check_diff_block(case, diffs, [Diff("diff", ["gone"], MISSING, "")])


def test_patch_ledger_balance():
    ledger_diffs = [ledger_diff("diff", ["balance"], 34, 3)]
    case = mod.PatchCase(FakeCase(), [], ledger_diffs)
    check_ledger_diffs(case, ledger_diffs)


def check_diff_block(case, diffs, patched_diffs=None):
    form = FakeForm(mod.get_diff_block(case))
    data = json.loads(unescape(form.form_data["diff"]))
    eq(data["case_id"], case.case_id)
    eq(data["diffs"], [mod.diff_to_json(y) for y in diffs])
    assert "ledgers" not in data, data

    assert_patched(form, patched_diffs or diffs)
    if patched_diffs:
        assert_patched(form, diffs, False)


def assert_patched(form, diffs, expect_patched=True):
    patch_diffs = [diff for diff in diffs
        if not mod.is_patchable(diff) or diff.old_value is MISSING]
    if not any(d.path[0] == "xform_ids" for d in patch_diffs):
        patch_diffs.append(Diff("set_mismatch", ["xform_ids", "[*]"], "old", "new"))
    with patch.object(casediff, "get_sql_forms", lambda x, **k: [form]):
        actual_patched = casediff.is_case_patched(FakeCase.case_id, patch_diffs)
    sep = "\n"
    assert actual_patched == expect_patched, (
        f"is_case_patched(case_id, diffs) -> {actual_patched}\n"
        f"{sep.join(repr(d) for d in patch_diffs)}\n\n{form.diff_block}"
    )


def check_ledger_diffs(case, diffs, patched_diffs=None):
    with patch.object(mod, "get_couch_transactions", lambda ref: [ref]), \
            patch("corehq.apps.commtrack.models.StockState.include_archived.filter"):
        form = FakeForm(mod.get_diff_block(case))
        data = json.loads(unescape(form.form_data["diff"]))
        eq(data["case_id"], case.case_id)
        eq(data["ledgers"], {"led/ger/ref": [ledger_json(y) for y in diffs]})
    assert "diffs" not in data, data


class FakeCase:
    case_id = "fake"
    closed = False


@attr.s
class FakeForm:
    diff_block = attr.ib()
    xmlns = mod.PatchForm.xmlns

    @property
    def form_data(self):
        xml = self.diff_block
        assert xml.startswith("<diff>"), xml
        assert xml.endswith("</diff>"), xml
        return {"diff": xml[6:-7]}


def ledger_diff(*args):
    ref = mod.UniqueLedgerReference.from_id("led/ger/ref")
    return mod.LedgerDiff(Diff(*args), ref)


def ledger_json(diff):
    data = mod.diff_to_json(diff)
    if data["path"] == ["balance"]:
        data["couch_transactions"] = [list(diff.ref)]
    return data
