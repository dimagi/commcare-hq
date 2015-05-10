import os
from jsonobject import JsonObject
import yaml
from corehq.apps.userreports.specs import TypeProperty
from corehq.apps.app_manager.models import Application
from dimagi.utils.decorators.memoized import memoized


class AbtSupervisorExpressionSpec(JsonObject):
    type = TypeProperty('abt_supervisor')
    _questions_cache = {}

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
        """
        Return the answer in the given submitted form (item) to the question specified by path.
        Return empty tuple if no answer was given to the given question.
        """
        if path:
            try:
                v = item['form']
                for key in path:
                    v = v[key]
                return v
            except KeyError:
                return ()

    @classmethod
    def _question_answered(cls, value):
        """
        Return true if the given value indicates that an answer was provided for its question.
        """
        return value != ()

    @classmethod
    def _raise_for_any_answer(cls, danger_value):
        """
        Return true if the given danger_value indicates that any question answer should raise the flag.
        """
        return danger_value == []

    @classmethod
    def _get_question_options(cls, item, question_path):
        """
        Return a list of option values for the given question path and item
        (which is a dict representation of an XFormInstance)
        """
        app_id, xmlns = item['app_id'], item['xmlns']
        questions = cls._questions_cache.get((app_id, xmlns), None)
        if questions is None:
            form = Application.get(app_id).get_form_by_xmlns(xmlns)
            questions = {
                q['value']: q for q in form.get_questions([], include_groups=True)
            }
            cls._questions_cache[(app_id, xmlns)] = questions

        question = questions.get('/data/' + "/".join(question_path), {})
        options = [o['value'] for o in question.get("options", [])]
        return options

    @classmethod
    def _get_unchecked(cls, xform_instance, question_path, answer, ignore=None):
        """
        Return the unchecked options in the given question.
        Do not return any which appear in the option ignore parameter.

        answer should be a string
        ignore should be a list of strings.
        """
        options = set(cls._get_question_options(xform_instance, question_path))
        checked = set(answer.split(" "))
        unchecked = options - checked
        ret = unchecked - set(ignore)
        return list(ret)

    def __call__(self, item, context=None):
        """
        Given a document (item), return a list of documents representing each
        of the flagged questions.
        """

        docs = []
        for spec in self._flag_specs.get(item['xmlns'], []):
            form_value = self._get_val(item, spec['question'])

            if spec.get("warning_type", None) == "unchecked":
                ignore = spec.get("ignore", [])
                unchecked = self._get_unchecked(item, spec['question'], form_value, ignore)
                if unchecked:
                    # Raise a flag because there are unchecked answers.
                    docs.append({
                        'flag': spec['question'][-1],
                        'warning': spec['warning'].format(msg=", ".join(unchecked))
                    })

            else:
                danger_value = spec.get('answer', [])
                if form_value == danger_value or (
                    self._question_answered(form_value) and
                    self._raise_for_any_answer(danger_value)
                ):
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
