from copy import copy
from StringIO import StringIO
from collections import namedtuple

from django.core.urlresolvers import reverse
from django.http import Http404
from django.utils.translation import ugettext_noop, ugettext_lazy as _
from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation
from django.views.generic import View

from corehq.apps.app_manager.exceptions import XFormException
from corehq.apps.app_manager.util import get_app_manager_template
from corehq.apps.app_manager.view_helpers import ApplicationViewMixin
from corehq.apps.app_manager.models import AdvancedForm, AdvancedModule, WORKFLOW_FORM
from corehq.apps.app_manager.xform import VELLUM_TYPES
from corehq.apps.domain.views import LoginAndDomainMixin
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.reports.formdetails.readable import FormQuestionResponse
from corehq.apps.style.decorators import use_angular_js
from couchexport.export import export_raw
from couchexport.models import Format
from couchexport.shortcuts import export_response


class AppSummaryView(JSONResponseMixin, LoginAndDomainMixin, BasePageView, ApplicationViewMixin):
    urlname = 'app_summary'
    page_title = ugettext_noop("Summary")
    template_name = 'app_manager/v1/summary.html'

    @use_angular_js
    def dispatch(self, request, *args, **kwargs):
        self.template_name = get_app_manager_template(
            self.domain,
            self.template_name,
            'app_manager/v2/summary.html',
        )
        return super(AppSummaryView, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        context = super(AppSummaryView, self).main_context
        context.update({
            'domain': self.domain,
        })
        return context

    @property
    def page_context(self):
        if not self.app or self.app.doc_type == 'RemoteApp':
            raise Http404()

        return {
            'VELLUM_TYPES': VELLUM_TYPES,
            'form_name_map': _get_name_map(self.app),
            'langs': self.app.langs,
            'app_id': self.app.id,
        }

    @property
    def parent_pages(self):
        return [
            {
                'title': _("Applications"),
                'url': reverse('view_app', args=[self.domain, self.app_id]),
            },
            {
                'title': self.app.name,
                'url': reverse('view_app', args=[self.domain, self.app_id]),
            }
        ]

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.app_id])

    @allow_remote_invocation
    def get_case_data(self, in_data):
        return {
            'response': self.app.get_case_metadata().to_json(),
            'success': True,
        }

    @allow_remote_invocation
    def get_form_data(self, in_data):
        modules = []
        errors = []
        for module in self.app.get_modules():
            forms = []
            module_meta = {
                'id': module.unique_id,
                'name': module.name,
                'short_comment': module.short_comment,
            }

            for form in module.get_forms():
                form_meta = {
                    'id': form.unique_id,
                    'name': form.name,
                    'short_comment': form.short_comment,
                }
                try:
                    questions = form.get_questions(
                        self.app.langs,
                        include_triggers=True,
                        include_groups=True,
                        include_translations=True
                    )
                    form_meta['questions'] = [FormQuestionResponse(q).to_json() for q in questions]
                except XFormException as e:
                    form_meta['error'] = {
                        'details': unicode(e),
                        'edit_url': reverse('form_source', args=[self.domain, self.app_id, module.id, form.id])
                    }
                    form_meta['module'] = copy(module_meta)
                    errors.append(form_meta)
                else:
                    forms.append(form_meta)

            module_meta['forms'] = forms
            modules.append(module_meta)
        return {
            'response': modules,
            'errors': errors,
            'success': True,
        }


def _get_name_map(app):
    name_map = {}
    for module in app.get_modules():
        name_map[module.unique_id] = module.name
        for form in module.get_forms():
            name_map[form.unique_id] = {
                'form_name': form.name,
                'module_name': module.name,
            }
    return name_map


def _translate_name(names, language):
    if not names:
        return u"[{}]".format(_("Unknown"))
    try:
        return names[language]
    except KeyError:
        first_name = names.iteritems().next()
        return u"{} [{}]".format(first_name[1], first_name[0])


def _get_translated_form_name(app, form_id, language):
    return _translate_name(_get_name_map(app)[form_id]['form_name'], language)


def _get_translated_module_name(app, module_id, language):
    return _translate_name(_get_name_map(app)[module_id], language)


APP_SUMMARY_EXPORT_HEADER_NAMES = [
    'app',
    'module',
    'form',
    'display_filter',
    'case_list_filter',
    'case_type',
    'case_actions',
    'filter',
    'module_type',
    'comments',
    'end_of_form_navigation',
    'parent_module',
]
AppSummaryRow = namedtuple('AppSummaryRow', APP_SUMMARY_EXPORT_HEADER_NAMES)
AppSummaryRow.__new__.__defaults__ = (None, ) * len(APP_SUMMARY_EXPORT_HEADER_NAMES)


class DownloadAppSummaryView(LoginAndDomainMixin, ApplicationViewMixin, View):
    urlname = 'download_app_summary'
    http_method_names = [u'get']

    def get(self, request, domain, app_id):
        language = request.GET.get('lang', 'en')
        headers = [(self.app.name, tuple(APP_SUMMARY_EXPORT_HEADER_NAMES))]
        data = [(self.app.name, [
            AppSummaryRow(
                app=self.app.name,
                comments=self.app.comment,
            )
        ])]

        for module in self.app.get_modules():
            try:
                case_list_filter = module.case_details.short.filter
            except AttributeError:
                case_list_filter = None

            data += [
                (self.app.name, [
                    AppSummaryRow(
                        app=self.app.name,
                        module=_get_translated_module_name(self.app, module.unique_id, language),
                        display_filter=module.module_filter,
                        case_type=module.case_type,
                        case_list_filter=case_list_filter,
                        case_actions=module.case_details.short.filter if hasattr(module, 'case_details') else None,
                        filter=module.module_filter,
                        module_type='advanced' if isinstance(module, AdvancedModule) else 'standard',
                        comments=module.comment,
                        parent_module=(_get_translated_module_name(self.app, module.root_module_id, language)
                                       if module.root_module_id else '')
                    )
                ])
            ]
            for form in module.get_forms():
                post_form_workflow = form.post_form_workflow
                if form.post_form_workflow == WORKFLOW_FORM:
                    post_form_workflow = u"form:\n{}".format(
                        u"\n".join(
                            [u"{form}: {xpath} [{datums}]".format(
                                form=_get_translated_form_name(self.app, link.form_id, language),
                                xpath=link.xpath,
                                datums=u", ".join(
                                    u"{}: {}".format(
                                        datum.name, datum.xpath
                                    ) for datum in link.datums)
                            ) for link in form.form_links]
                        )
                    )
                data += [
                    (self.app.name, [
                        AppSummaryRow(
                            app=self.app.name,
                            module=_get_translated_module_name(self.app, module.unique_id, language),
                            form=_get_translated_form_name(self.app, form.get_unique_id(), language),
                            display_filter=form.form_filter,
                            case_type=form.get_case_type(),
                            case_actions=self._get_form_actions(form),
                            filter=form.form_filter,
                            module_type='advanced' if isinstance(module, AdvancedModule) else 'standard',
                            comments=form.comment,
                            end_of_form_navigation=post_form_workflow,
                        )
                    ])
                ]

        export_string = StringIO()
        export_raw(tuple(headers), data, export_string, Format.XLS_2007),
        return export_response(
            export_string,
            Format.XLS_2007,
            u'{app_name} v.{app_version} - App Summary ({lang})'.format(
                app_name=self.app.name,
                app_version=self.app.version,
                lang=language
            ),
        )

    def _get_form_actions(self, form):
        update_types = {
            'AdvancedOpenCaseAction': 'open',
            'LoadUpdateAction': 'update',
        }

        if isinstance(form, AdvancedForm):
            return "\n".join([
                "{action_type}: {case_type} [{case_tag}]".format(
                    action_type=update_types[type(action).__name__],
                    case_type=action.case_type,
                    case_tag=action.case_tag,
                )
                for action in form.actions.get_all_actions()
            ])
        else:
            return form.get_action_type()


FORM_SUMMARY_EXPORT_HEADER_NAMES = [
    "question_id",
    "label",
    "translations",
    "type",
    "repeat",
    "group",
    "options",
    "calculate",
    "relevant",
    "required",
    "comment",
]
FormSummaryRow = namedtuple('FormSummaryRow', FORM_SUMMARY_EXPORT_HEADER_NAMES)
FormSummaryRow.__new__.__defaults__ = (None, ) * len(FORM_SUMMARY_EXPORT_HEADER_NAMES)


class DownloadFormSummaryView(LoginAndDomainMixin, ApplicationViewMixin, View):
    urlname = 'download_form_summary'
    http_method_names = [u'get']

    def get(self, request, domain, app_id):
        language = request.GET.get('lang', 'en')
        modules = list(self.app.get_modules())
        headers = [('All Forms', ('module_name', 'form_name', 'comment'))]
        headers += [
            (self._get_form_sheet_name(module, form, language), tuple(FORM_SUMMARY_EXPORT_HEADER_NAMES))
            for module in modules for form in module.get_forms()
        ]
        data = list((
            'All Forms',
            self.get_all_forms_row(module, form, language)
        ) for module in modules for form in module.get_forms())
        data += list(
            (self._get_form_sheet_name(module, form, language), self._get_form_row(form, language))
            for module in modules for form in module.get_forms()
        )
        export_string = StringIO()
        export_raw(tuple(headers), data, export_string, Format.XLS_2007),
        return export_response(
            export_string,
            Format.XLS_2007,
            u'{app_name} v.{app_version} - Form Summary ({lang})'.format(
                app_name=self.app.name,
                app_version=self.app.version,
                lang=language
            ),
        )

    def _get_form_row(self, form, language):
        form_summary_rows = []
        for question in form.get_questions(
            self.app.langs,
            include_triggers=True,
            include_groups=True,
            include_translations=True
        ):
            question_response = FormQuestionResponse(question)
            form_summary_rows.append(
                FormSummaryRow(
                    question_id=question_response.value,
                    label=_translate_name(question_response.translations, language),
                    translations=question_response.translations,
                    type=question_response.type,
                    repeat=question_response.repeat,
                    group=question_response.group,
                    options="\n".join(
                        [u"{} - {}".format(_translate_name(option.translations, language), option.value)
                         for option in question_response.options]
                    ),
                    calculate=question_response.calculate,
                    relevant=question_response.relevant,
                    required="true" if question_response.required else "false",
                    comment=question_response.comment,
                )
            )
        return tuple(form_summary_rows)

    def _get_form_sheet_name(self, module, form, language):
        return u"{} - {}".format(
            _get_translated_module_name(self.app, module.unique_id, language),
            _get_translated_form_name(self.app, form.get_unique_id(), language),
        )

    def get_all_forms_row(self, module, form, language):
        return ((
            _get_translated_module_name(self.app, module.unique_id, language),
            _get_translated_form_name(self.app, form.get_unique_id(), language),
            form.short_comment
        ),)

CASE_SUMMARY_EXPORT_HEADER_NAMES = [
    'case_property_name',
    'form_id',
    'form_name',
    'load_question_question',
    'load_question_condition',
    'save_question_question',
    'save_question_condition',
    'save_question_calculate',
]
PropertyRow = namedtuple('PropertyRow', CASE_SUMMARY_EXPORT_HEADER_NAMES)


class DownloadCaseSummaryView(LoginAndDomainMixin, ApplicationViewMixin, View):
    urlname = 'download_case_summary'
    http_method_names = [u'get']

    def get(self, request, domain, app_id):
        case_metadata = self.app.get_case_metadata()
        language = request.GET.get('lang', 'en')

        headers = [('All Case Properties', ('case_type', 'case_property'))]
        headers += list((
            case_type.name,
            tuple(CASE_SUMMARY_EXPORT_HEADER_NAMES)
        )for case_type in case_metadata.case_types)

        data = list((
            'All Case Properties',
            self.get_case_property_rows(case_type)
        ) for case_type in case_metadata.case_types)
        data += list((
            case_type.name,
            self.get_case_questions_rows(case_type, language)
        ) for case_type in case_metadata.case_types)

        export_string = StringIO()
        export_raw(tuple(headers), data, export_string, Format.XLS_2007),
        return export_response(
            export_string,
            Format.XLS_2007,
            u'{app_name} v.{app_version} - Case Summary ({lang})'.format(
                app_name=self.app.name,
                app_version=self.app.version,
                lang=language
            ),
        )

    def get_case_property_rows(self, case_type):
        return tuple((case_type.name, prop.name) for prop in case_type.properties)

    def get_case_questions_rows(self, case_type, language):
        rows = []
        for prop in case_type.properties:
            for form in prop.forms:
                for load_question in form.load_questions:
                    rows.append(self._get_load_question_row(prop, form, language, load_question))
                for save_question in form.save_questions:
                    rows.append(self._get_save_question_row(prop, form, language, save_question))

        return tuple(rows)

    def _get_load_question_row(self, prop, form, language, load_question):
        return PropertyRow(
            prop.name,
            form.form_id,
            _get_translated_form_name(self.app, form.form_id, language),
            load_question.question.value,
            "{} {} {}".format(
                load_question.condition.question,
                load_question.condition.operator,
                load_question.condition.answer
            ) if load_question.condition else "",
            None,
            None,
            None,
        )

    def _get_save_question_row(self, prop, form, language, save_question):
        return PropertyRow(
            prop.name,
            form.form_id,
            _get_translated_form_name(self.app, form.form_id, language),
            None,
            None,
            save_question.question.value,
            "{} {} {}".format(
                save_question.condition.question,
                save_question.condition.operator,
                save_question.condition.answer
            ) if save_question.condition else "",
            save_question.question.calculate,
        )
