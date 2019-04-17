from __future__ import absolute_import
from __future__ import unicode_literals

from testil import assert_raises

from corehq.apps.tzmigration.timezonemigration import FormJsonDiff, MISSING

from ..diffrule import ANY, Ignore


def test_rules():
    diff = FormJsonDiff("diff", ("node",), "old", "new")
    old_obj = {"node": "old", "flag": True}
    new_obj = {"node": "new", "is_val": True}

    def match(rule):
        assert rule.matches(diff, old_obj, new_obj), (rule, diff)

    def no_match(rule):
        assert not rule.matches(diff, old_obj, new_obj), (rule, diff)

    yield match, Ignore("diff", ("node",), old="old", new="new")
    yield match, Ignore("diff", "node", old="old", new="new")
    yield match, Ignore(ANY, "node", old="old", new="new")
    yield match, Ignore("diff", ANY, old="old", new="new")
    yield match, Ignore("diff", (ANY,), old="old", new="new")
    yield match, Ignore("diff", "node", old=ANY, new="new")
    yield match, Ignore("diff", "node", old="old", new=ANY)
    yield match, Ignore("diff", "node", old="old")
    yield match, Ignore("diff", "node")
    yield match, Ignore("diff")
    yield match, Ignore(type="diff")
    yield match, Ignore(path="node")
    yield match, Ignore(old="old")
    yield match, Ignore(new="new")
    yield match, Ignore()

    yield no_match, Ignore(type="miss")
    yield no_match, Ignore(path=("key",))
    yield no_match, Ignore(path="key")
    yield no_match, Ignore(old=1)
    yield no_match, Ignore(new=2)
    yield no_match, Ignore(old=MISSING)
    yield no_match, Ignore(new=MISSING)

    def is_flagged(old, new, rule, diff_):
        assert old is old_obj, old
        assert new is new_obj, new
        assert rule is check_rule, rule
        assert diff_ is diff, diff_
        return old["flag"]

    check_rule = Ignore("diff", "node", old="old", new="new", check=is_flagged)
    yield match, check_rule

    def nope(old_obj, new_obj, rule, diff):
        return False

    yield no_match, Ignore("diff", "node", old="old", new="new", check=nope)


def test_missing_rules():
    old_obj = {"flag": True}
    new_obj = {"is_val": True}

    def match(rule, diff):
        assert rule.matches(diff, old_obj, new_obj), (rule, diff)

    yield (
        match,
        Ignore("diff", "flag", old=True, new=MISSING),
        FormJsonDiff("diff", ("flag",), True, MISSING),
    )

    yield (
        match,
        Ignore("diff", "is_val", old=MISSING, new=True),
        FormJsonDiff("diff", ("is_val",), MISSING, True),
    )


def test_multi_element_path_rules():
    diff = FormJsonDiff("diff", ("data", "num"), 1, 2)
    old_obj = {"data": {"num": 1}}
    new_obj = {"data": {"num": 2}}

    def match(rule):
        assert rule.matches(diff, old_obj, new_obj), (rule, diff)

    def no_match(rule):
        assert not rule.matches(diff, old_obj, new_obj), (rule, diff)

    yield match, Ignore("diff", (ANY, "num"), old=1, new=2)
    yield match, Ignore("diff", ("data", ANY), old=1, new=2)
    yield match, Ignore("diff", ANY, old=1, new=2)

    yield no_match, Ignore("diff", (ANY,), old=1, new=2)
    yield no_match, Ignore("diff", (ANY, ANY, ANY), old=1, new=2)


def test_any_not_hashable():
    def test(path):
        with assert_raises(TypeError):
            {}[path] = None

    yield test, ANY
    yield test, ("path", ANY)
