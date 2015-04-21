from collections import namedtuple
from jsonobject import JsonObject
from corehq.apps.userreports.specs import TypeProperty
from dimagi.utils.decorators.memoized import memoized


class AbtSupervisorExpressionSpec(JsonObject):
    type = TypeProperty('abt_supervisor')

    @property
    @memoized
    def _flag_specs(self):
        FlagSpec = namedtuple("FlagSpec", [
            "form_xmlns",
            "flag_id",
            "path",
            "danger_value",
            "warning_string",
            "warning_property_path"
        ])
        return [
            FlagSpec(
                form_xmlns="http://openrosa.org/formdesigner/BB2BF979-BD8F-4B8D-BCF8-A46451228BA9",
                flag_id="adequate_distance",
                path=["q2"],
                danger_value="No",
                warning_string="The nearest sensitive receptor is {msg} meters away",
                warning_property_path=['q2_next']
            ),
            FlagSpec(
                form_xmlns="http://openrosa.org/formdesigner/BB2BF979-BD8F-4B8D-BCF8-A46451228BA9",
                flag_id="leak_free",
                path=["q5"],
                danger_value="No",
                warning_string="The leak will be repaired on {msg}",
                warning_property_path=['q5_action_two']
            ),
            FlagSpec(
                form_xmlns="dummy",
                flag_id="dummy flag",
                path=["dummy"],
                danger_value="dummy",
                warning_string="foo{msg}",
                warning_property_path=['bloop']
            ),
            FlagSpec(
                form_xmlns="http://openrosa.org/formdesigner/54338047-CFB6-4D5B-861B-2256A10BBBC8",
                flag_id="eaten_breakfast",
                path=["q2"],
                danger_value="No",
                warning_string="{msg}",
                warning_property_path=['nothing_pls']
            )
        ]

    def __call__(self, item, context=None):
        """
        Given a document (item), return a list of documents representing each
        of the flagged questions.
        """
        # TODO: Don't define FlagSpec and get_val for every call

        def get_val(item, path):
            try:
                v = item['form']
                for key in path:
                    v = v[key]
                return v
            except KeyError:
                return None

        docs = []
        print item['xmlns']
        for spec in self._flag_specs:
            if item['xmlns'] == spec.form_xmlns:
                if get_val(item, spec.path) == spec.danger_value:
                    docs.append({
                        'flag': spec.flag_id,
                        'warning': spec.warning_string.format(
                            msg=get_val(item, spec.warning_property_path) or ""
                        )
                    })
        return docs


def abt_supervisor_expression(spec, context):
    wrapped = AbtSupervisorExpressionSpec.wrap(spec)
    return wrapped
