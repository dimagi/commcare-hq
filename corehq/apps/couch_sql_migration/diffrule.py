from __future__ import absolute_import
from __future__ import unicode_literals

import attr
import six


class AnyType(object):

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    def __repr__(self):
        return "ANY"

    __hash__ = None


ANY = AnyType()


@attr.s
class Ignore(object):
    """Ignore rule

    The `MISSING` constant referenced here is defined in
    `corehq.apps.tzmigration.timezonemigration`.

    :param type: Diff type to match (string or `ANY`).
    :param path: Diff path to match (string, tuple, or `ANY`). A string
    is shorthand for a single-element path. Stand-alone `ANY` matches
    all paths. Each element in a tuple must be a string or `ANY`. `ANY`
    within a tuple acts as wildcard matching a single element in the
    same position.
    :param old: Old value, `ANY` or `MISSING`.
    :param new: New value, `ANY` or `MISSING`.
    :param check: A predicate function accepting four arguments
    `(old_obj, new_obj, ignore_rule, diff_object)` and returning a bool.
    The default predicate returns true, which means diffs having all
    other matching comparisons are ignored by default.
    """

    def _convert_path(value):
        if isinstance(value, six.text_type):
            return (value,)
        if value is ANY:
            return value
        assert all(isinstance(v, six.text_type) or v is ANY for v in value), \
            "invalid path: {}".format(value)
        assert isinstance(value, tuple) or value is ANY, repr(value)
        return value

    type = attr.ib(default=ANY)
    path = attr.ib(default=ANY, converter=_convert_path)
    old = attr.ib(default=ANY)
    new = attr.ib(default=ANY)
    check = attr.ib(default=lambda old_obj, new_obj, rule, diff: True)

    def matches(self, diff, old_obj, new_obj):
        """Determine if the given diff can be ignored

        Match any diff having a matching `diff_type`, `path`, `old_value`,
        `new_value`, and for which this rule's check predicate returns true.

        :param diff: `FormJsonDiff` object.
        :param old_obj: Old object (JSON-encodable).
        :param new_obj: New object (JSON-encodable).
        :returns: True if the diff can be ignored otherwise false.
        """
        return (
            self.type == diff.diff_type and
            self.path == diff.path and
            self.old == diff.old_value and
            self.new == diff.new_value and
            self.check(old_obj, new_obj, self, diff)
        )
