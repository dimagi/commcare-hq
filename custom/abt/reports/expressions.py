import os

from django.utils.functional import cached_property
from jsonobject import JsonObject
import yaml
from corehq.apps.userreports.specs import TypeProperty
from corehq.apps.app_manager.models import Application
from corehq.util.quickcache import quickcache


class AbtExpressionSpec(JsonObject):
    domain = None
    _flagspec_filename = None

    @cached_property
    def _flag_specs(self):
        """
        Return a dict where keys are form xmlns and values are lists of FlagSpecs
        """
        path = os.path.join(os.path.dirname(__file__), self._flagspec_filename)
        with open(path, encoding='utf-8') as f:
            return yaml.safe_load(f)

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
    @quickcache(['app_id', 'xmlns'])
    def _get_form(cls, app_id, xmlns):
        for form in Application.get(app_id).get_forms():
            if form['xmlns'] == xmlns:
                return form

    @classmethod
    @quickcache(['app_id', 'xmlns', 'lang'])
    def _get_questions(cls, app_id, xmlns, lang):
        questions = Application.get(app_id).get_questions(xmlns, [lang], include_groups=True)
        return {q['value']: q for q in questions}

    @classmethod
    def _get_question_options(cls, item, question_path, section='data'):
        """
        Return a list of option values for the given question path and item
        (which is a dict representation of an XFormInstance)
        """
        questions = cls._get_questions(item['app_id'], item['xmlns'], cls._get_language(item))
        question = questions.get('/' + section + '/' + "/".join(question_path), {})
        return question.get("options", [])

    @classmethod
    def _get_form_name(cls, item):
        form = cls._get_form(item['app_id'], item['xmlns'])
        lang = cls._get_language(item)
        if lang in form.name:
            return form.name[lang]
        else:
            return form.name['en']

    @classmethod
    def _get_unchecked(cls, xform_instance, question_path, answer, ignore=None, section='data'):
        """
        Return the unchecked options in the given question.
        Do not return any which appear in the option ignore parameter.

        answer should be a string
        ignore should be a list of strings.
        """
        answer = answer or ""
        options = {
            o['value']: o['label'] for o in cls._get_question_options(xform_instance, question_path, section)
        }
        checked = set(answer.split(" "))
        unchecked = set(options.keys()) - checked
        relevant_unchecked = unchecked - set(ignore)
        return [options[u] for u in relevant_unchecked]

    @classmethod
    def _get_comments(cls, item, spec):
        """
        Return the comments for the question specified in the spec.
        If the spec does not contain a `comment` field, then the `question`
        field is used to build the path to the comment question.
        """
        comments_question = spec.get('comment', False)
        question_path = spec["question"]

        if not comments_question:
            parts = question_path[-1].split("_")
            parts.insert(1, "comments")
            comments_question = question_path[:-1] + ["_".join(parts)]

        if cls.comment_from_root:
            comments_question = spec.get("base_path")[:-1] + comments_question

        comments = cls._get_val(item, comments_question)
        return comments if comments != () else ""

    @classmethod
    def _get_language(cls, item):
        """
        Return the language in which this row should be rendered.
        """
        french_domains = (
            "airsmadagascar",
            "abtmali",
            "vectorlink-burkina-faso",
            "vectorlink-benin",
            "vectorlink-madagascar",
            "pmievolve-madagascar",
            "vectorlink-mali",
        )

        if item.get("domain", None) in french_domains:
            return "fra"
        country = cls._get_val(item, ["location_data", "country"])
        if country in ["Senegal", 'S\xe9n\xe9gal', "Benin", "Mali", "Madagascar"]:
            return "fra"
        elif country in ["mozambique", "Mozambique"]:
            return "por"
        return "en"

    @classmethod
    def _get_warning(cls, spec, item):
        default = str(spec.get("warning", ""))
        language = cls._get_language(item)
        warning_key_map = {
            "fra": "warning_fr",
            "por": "warning_por",
            "en": "warning"
        }
        warning = str(spec.get(warning_key_map[language], default))
        return warning if warning else default

    @classmethod
    def _get_inspector_names(cls, item):
        repeat_items = cls._get_val(item, ['employee_group', 'employee'])
        if repeat_items == ():
            return ""
        if type(repeat_items) != list:
            repeat_items = [repeat_items]
        repeat_items = [{'form': x} for x in repeat_items]

        names = []
        for i in repeat_items:
            for q in ['other_abt_employee_name', 'abt_employee_name', 'other_non-abt_employee_name']:
                name = cls._get_val(i, ['abt_emp_list', q])
                if name:
                    names.append(name)
                    break

        return ", ".join(names)

    @classmethod
    def _get_flag_name(cls, item, spec):
        """
        Return value that should be in the flag column. Defaults to the
        question id if spec doesn't specify something else.
        """
        default = spec['question'][-1]
        flag_name_key_map = {
            "fra": "flag_name_fr",
            "por": "flag_name_por",
            "en": "flag_name",
        }
        lang = cls._get_language(item)
        name = spec.get(flag_name_key_map[lang], None)
        return name if name else default

    @classmethod
    def _get_responsible_follow_up(self, spec):
        return spec.get('responsible_follow_up', "")

    def __call__(self, item, evaluation_context=None):
        """
        Given a document (item), return a list of documents representing each
        of the flagged questions.
        """
        names = self._get_inspector_names(item)
        docs = []
        self.domain = item.get('domain', None)
        for spec in self._flag_specs.get(item['xmlns'], []):

            if spec.get("base_path", False):
                repeat_items = self._get_val(item, spec['base_path'])
                if repeat_items == ():
                    repeat_items = []
                if type(repeat_items) != list:
                    # bases will be a dict if the repeat only happened once.
                    repeat_items = [repeat_items]
                # We have to add the 'form' key here so that _get_val works correctly.
                repeat_items = [{'form': x} for x in repeat_items]
            else:
                repeat_items = [item]

            # Iterate over the repeat items, or the single submission
            for partial in repeat_items:

                if not names:
                    # Update inspector names if don't find by _get_inspector_names because in
                    # app for 2019 we have new place for this data there is already a string
                    # with all names joined by ','
                    names = self._get_val(item, ['supervisor_group', 'join_supervisor_name'])

                form_value = self._get_val(partial, spec['question'])
                warning_type = spec.get("warning_type", None)

                if warning_type == "unchecked" and form_value:
                    # Don't raise flag if no answer given
                    ignore = spec.get("ignore", [])
                    section = spec.get("section", "data")
                    unchecked = self._get_unchecked(
                        item,
                        spec.get('base_path', []) + spec['question'],
                        form_value,
                        ignore,
                        section
                    )
                    if unchecked:
                        # Raise a flag because there are unchecked answers.
                        docs.append({
                            'flag': self._get_flag_name(item, spec),
                            'warning': self._get_warning(spec, item).format(msg=", ".join(unchecked)),
                            'comments': self._get_comments(
                                partial if not self.comment_from_root else item,
                                spec
                            ),
                            'names': names,
                            'form_name': self._get_form_name(item),
                            'responsible_follow_up': self._get_responsible_follow_up(spec)
                        })

                elif warning_type == "unchecked_special" and form_value:
                    # Don't raise flag if no answer given
                    ignore = spec.get("ignore", [])
                    section = spec.get("section", "data")
                    master_value = self._get_val(item, ['insecticide_prep_grp', 'Q10', 'sop_full_ppe'])
                    second_unchecked = self._get_unchecked(
                        item,
                        spec.get('base_path', []) + spec['question'],
                        form_value,
                        ignore,
                        section
                    )
                    if not master_value and second_unchecked:
                        # Raise a flag because master question is not answered but duplicate question is.
                        docs.append({
                            'flag': self._get_flag_name(item, spec),
                            'warning': self._get_warning(spec, item).format(msg=", ".join(second_unchecked)),
                            'comments': self._get_comments(
                                partial if not self.comment_from_root else item,
                                spec
                            ),
                            'names': names,
                            'form_name': self._get_form_name(item),
                            'responsible_follow_up': self._get_responsible_follow_up(spec)
                        })

                elif warning_type == "q3_special" and form_value:
                    # One of the questions doesn't follow the same format as the
                    # others, hence this special case.
                    missing_items = ""
                    if form_value == "only_license":
                        missing_items = "cell"
                    if form_value == "only_cell":
                        missing_items = "license"
                    if form_value == "none":
                        missing_items = "cell, license"
                    if missing_items:
                        docs.append({
                            'flag': self._get_flag_name(item, spec),
                            'warning': self._get_warning(spec, item).format(msg=missing_items),
                            'comments': self._get_comments(
                                partial if not self.comment_from_root else item,
                                spec
                            ),
                            'names': names,
                            'form_name': self._get_form_name(item),
                            'responsible_follow_up': self._get_responsible_follow_up(spec)
                        })
                elif warning_type == "not_selected" and form_value:
                    value = spec.get("value", "")
                    if form_value and value not in form_value:
                        warning_question_data = partial if not spec.get('warning_question_root', False) else item
                        docs.append({
                            'flag': self._get_flag_name(item, spec),
                            'warning': self._get_warning(spec, item).format(
                                msg=self._get_val(warning_question_data, spec.get('warning_question', None)) or ""
                            ),
                            'comments': self._get_comments(
                                partial if not self.comment_from_root else item,
                                spec
                            ),
                            'names': names,
                            'form_name': self._get_form_name(item),
                            'responsible_follow_up': self._get_responsible_follow_up(spec)
                        })

                else:
                    danger_value = spec.get('answer', [])
                    if form_value == danger_value or (
                        self._question_answered(form_value) and
                        self._raise_for_any_answer(danger_value)
                    ):
                        warning_question_data = partial if not spec.get('warning_question_root', False) else item
                        docs.append({
                            'flag': self._get_flag_name(item, spec),
                            'warning': self._get_warning(spec, item).format(
                                msg=self._get_val(warning_question_data, spec.get('warning_question', None)) or ""
                            ),
                            'comments': self._get_comments(
                                partial if not self.comment_from_root else item,
                                spec
                            ),
                            'names': names,
                            'form_name': self._get_form_name(item),
                            'responsible_follow_up': self._get_responsible_follow_up(spec)
                        })

        return docs


class AbtSupervisorExpressionSpec(AbtExpressionSpec):
    type = TypeProperty('abt_supervisor')
    comment_from_root = False

    @property
    def _flagspec_filename(self):
        if self.domain == 'vectorlink-uganda':
            return 'flagspecs_uganda.yml'
        else:
            return 'flagspecs.yml'


class AbtSupervisorV2ExpressionSpec(AbtExpressionSpec):
    type = TypeProperty('abt_supervisor_v2')
    _flagspec_filename = 'flagspecs_v2.yml'
    comment_from_root = True


class AbtSupervisorV2019ExpressionSpec(AbtExpressionSpec):
    type = TypeProperty('abt_supervisor_v2019')
    _flagspec_filename = 'flagspecs_v2019.yml'
    comment_from_root = True


class AbtSupervisorV2020ExpressionSpec(AbtExpressionSpec):
    type = TypeProperty('abt_supervisor_v2020')
    _flagspec_filename = 'flagspecs_v2020.yml'
    comment_from_root = True


def abt_supervisor_expression(spec, factory_context):
    return AbtSupervisorExpressionSpec.wrap(spec)


def abt_supervisor_v2_expression(spec, factory_context):
    return AbtSupervisorV2ExpressionSpec.wrap(spec)


def abt_supervisor_v2019_expression(spec, factory_context):
    return AbtSupervisorV2019ExpressionSpec.wrap(spec)


def abt_supervisor_v2020_expression(spec, factory_context):
    return AbtSupervisorV2020ExpressionSpec.wrap(spec)
