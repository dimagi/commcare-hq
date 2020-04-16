from testil import assert_raises, eq

from corehq.apps.tzmigration.timezonemigration import FormJsonDiff as Diff

from .. import casepatch as mod


def test_cannot_patch_opened_by_alone():
    diffs = [Diff("diff", ["opened_by"], "old", "new")]
    with assert_raises(mod.CannotPatch):
        mod.PatchCase(FakeCase(), diffs)


def test_can_patch_opened_by_with_user_id():
    diffs = [
        Diff("diff", ["opened_by"], "old", "new"),
        Diff("diff", ["user_id"], "old", "new"),
    ]
    case = mod.PatchCase(FakeCase(), diffs)
    eq(case.dynamic_case_properties(), {})


class FakeCase:
    case_id = "fake"
    closed = False
