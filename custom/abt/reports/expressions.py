import os
from jsonobject import JsonObject
import yaml
from corehq.apps.userreports.specs import TypeProperty
from dimagi.utils.decorators.memoized import memoized


class AbtSupervisorExpressionSpec(JsonObject):
    type = TypeProperty('abt_supervisor')

    @property
    @memoized
    def _flag_specs(self):
        """
        Return a dict where keys are form xmlns and values are lists of FlagSpecs
        """
        path = os.path.join(os.path.dirname(__file__), 'flagspecs.yaml')
        with open(path) as f:
            return yaml.load(f)

    @classmethod
    def _get_val(cls, item, path):
        '''
        Return empty tuple if path is not in item
        '''
        if path:
            try:
                v = item['form']
                for key in path:
                    v = v[key]
                return v
            except KeyError:
                return ()

    def __call__(self, item, context=None):
        """
        Given a document (item), return a list of documents representing each
        of the flagged questions.
        """

        docs = []
        for spec in self._flag_specs.get(item['xmlns'], []):
            form_value = self._get_val(item, spec['question'])
            danger_value = spec.get('answer', [])
            if form_value == danger_value or (form_value != () and danger_value == []):
                docs.append({
                    'flag': spec['question'][-1],
                    'warning': spec['warning'].format(
                        msg=self._get_val(item, spec.get('warning_question', None)) or ""
                    )
                })
        return docs


def abt_supervisor_expression(spec, context):
    wrapped = AbtSupervisorExpressionSpec.wrap(spec)
    return wrapped
