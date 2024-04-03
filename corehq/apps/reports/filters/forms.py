from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop

from couchdbkit.exceptions import ResourceNotFound
from memoized import memoized

from couchforms.analytics import (
    get_all_xmlns_app_id_pairs_submitted_to_in_domain,
)

from corehq.apps.app_manager.models import Application
from corehq.apps.hqcase.utils import SYSTEM_FORM_XMLNS_MAP
from corehq.apps.hqwebapp.utils.translation import (
    format_html_lazy,
    mark_safe_lazy,
)
from corehq.apps.reports.analytics.couchaccessors import (
    get_all_form_definitions_grouped_by_app_and_xmlns,
    get_all_form_details,
    get_form_details_for_app,
    get_form_details_for_app_and_module,
    get_form_details_for_app_and_xmlns,
    get_form_details_for_xmlns,
)
from corehq.apps.reports.analytics.esaccessors import (
    guess_form_name_from_submissions_using_xmlns,
)
from corehq.apps.reports.filters.base import (
    BaseDrilldownOptionFilter,
    BaseSingleOptionFilter,
)
from corehq.const import MISSING_APP_ID
from corehq.elastic import ESError
from corehq.util.context_processors import commcare_hq_names

PARAM_SLUG_STATUS = 'status'
PARAM_SLUG_APP_ID = 'app_id'
PARAM_SLUG_MODULE = 'module'
PARAM_SLUG_XMLNS = 'xmlns'

PARAM_VALUE_STATUS_ACTIVE = 'active'
PARAM_VALUE_STATUS_DELETED = 'deleted'


class FormsByApplicationFilterParams(object):

    def __init__(self, params):
        self.app_id = self.status = self.module = self.xmlns = self.most_granular_filter = None
        for param in params:
            slug = param['slug']
            value = param['value']
            if slug == PARAM_SLUG_STATUS:
                self.status = value
            elif slug == PARAM_SLUG_APP_ID:
                self.app_id = value
            elif slug == PARAM_SLUG_MODULE:
                self.module = value
            elif slug == PARAM_SLUG_XMLNS:
                self.xmlns = value
            # we rely on the fact that the filters come in order of granularity
            # some logic depends on this
            self.most_granular_filter = slug

    @property
    def show_active(self):
        return self.status == PARAM_VALUE_STATUS_ACTIVE

    def get_module_int(self):
        try:
            return int(self.module)
        except ValueError:
            return None


class FormsByApplicationFilter(BaseDrilldownOptionFilter):
    """
        Use this filter to drill down by
        (Active Applications or Deleted Applications >) Application > Module > Form

        You may also select Unknown Forms for forms that can't be matched to any known Application or
        Application-Deleted for this domain. Form submissions for remote apps will also show up
        in Unknown Forms

        You may also hide/show fuzzy results (where fuzzy means you can't match that XMLNS to exactly one
        Application or Application-Deleted).
    """
    slug = "form"
    label = gettext_lazy("Filter Forms")
    css_class = "span5"
    drilldown_empty_text = gettext_lazy("You don't have any applications set up, so there are no forms "
                                        "to choose from. Please create an application!")
    template = "reports/filters/bootstrap3/form_app_module_drilldown.html"
    unknown_slug = "unknown"
    fuzzy_slug = "@@FUZZY"
    show_global_hide_fuzzy_checkbox = True
    display_app_type = False  # whether we're displaying the application type select box in the filter

    @property
    def display_lang(self):
        """
            This should return the lang code of the language being used to view this form.
        """
        return hasattr(self.request, 'couch_user') and self.request.couch_user.language or 'en'

    @property
    def rendered_labels(self):
        """
            Here we determine whether to extend the drilldown to allow the user to choose application types.
            Current supported types are:
            - Active Application (Application)
            - Deleted Application (Application-Deleted)
        """
        labels = self.get_labels()
        if self.drilldown_map and self.drilldown_map[0]['val'] == PARAM_VALUE_STATUS_ACTIVE:
            labels = [
                (_('Application Type'),
                 _("Select an Application Type") if self.use_only_last else _("Show all Application Types"),
                 'status'),
                (_('Application'),
                 _("Select Application...") if self.use_only_last else _(
                     "Show all Forms of this Application Type..."),
                 PARAM_SLUG_APP_ID),
            ] + labels[1:]
        return labels

    @property
    def filter_context(self):
        context = super(FormsByApplicationFilter, self).filter_context
        context.update({
            'unknown_available': bool(self._unknown_forms),
            'unknown': {
                'show': bool(self._show_unknown),
                'slug': self.unknown_slug,
                'selected': self._selected_unknown_xmlns,
                'options': self._unknown_forms_options,
                'default_text': "Select an Unknown Form..." if self.use_only_last else "Show All Unknown Forms...",
            },
            'hide_fuzzy': {
                'show': not self._show_unknown and self.show_global_hide_fuzzy_checkbox and self._fuzzy_forms,
                'slug': '%s_%s' % (self.slug, self.fuzzy_slug),
                'checked': self._hide_fuzzy_results,
            },
            'display_app_type': self.display_app_type,
            'all_form_retrieval_failed': self.all_form_retrieval_failed,
        })

        show_advanced = self.request.GET.get('show_advanced') == 'on'

        #set Default app type to active only when advanced option is not selected
        if self.display_app_type and not context['selected'] and not show_advanced:
            context['selected'] = [PARAM_VALUE_STATUS_ACTIVE]

        context["show_advanced"] = (
            show_advanced
            or context["unknown"]["show"]
            or context["hide_fuzzy"]["checked"]
            or (len(context['selected']) > 0
                and context['selected'][0] == PARAM_VALUE_STATUS_DELETED
                )
        )
        return context

    @property
    @memoized
    def drilldown_map(self):
        final_map = []
        map_active = []
        map_deleted = []

        all_forms = self._application_forms_info.copy()

        for app_map in all_forms.values():
            is_deleted = app_map['is_deleted']

            def _translate_name(item):
                return self.get_translated_value(self.display_lang, app_map['app']['langs'], item)

            app_name = _translate_name(app_map['app']['names'])
            if is_deleted:
                app_name = "%s [Deleted Application]" % app_name
            app = self._map_structure(app_map['app']['id'], app_name)

            for module_map in sorted(app_map['modules'],
                                     key=lambda item: _translate_name(item['module']['names']).lower()
                                     if item['module'] else ''):
                if module_map['module'] is not None:
                    module_name = _translate_name(module_map['module']['names'])
                    module = self._map_structure(module_map['module']['id'], module_name)
                    for form_map in sorted(module_map['forms'],
                                           key=lambda item: _translate_name(item['form']['names']).lower()):
                        form_name = _translate_name(form_map['form']['names'])
                        module['next'].append(self._map_structure(form_map['xmlns'], form_name))
                    app['next'].append(module)

            if is_deleted:
                map_deleted.append(app)
            else:
                map_active.append(app)

        # sort apps by name
        map_active = sorted(map_active, key=lambda item: item['text'].lower())
        map_deleted = sorted(map_deleted, key=lambda item: item['text'].lower())

        if (bool(map_deleted) + bool(map_active)) > 1:
            self.display_app_type = True
            if map_active:
                final_map.append(
                    self._map_structure(PARAM_VALUE_STATUS_ACTIVE, _('Active CommCare Applications'), map_active)
                )
            if map_deleted:
                final_map.append(
                    self._map_structure(PARAM_VALUE_STATUS_DELETED, _('Deleted CommCare Applications'),
                                        map_deleted)
                )
        else:
            final_map.extend(map_active or map_deleted)

        return final_map

    @property
    def all_form_retrieval_failed(self):
        return getattr(self, '_all_form_retrieval_failed', False)

    @property
    @memoized
    def _all_forms(self):
        """
        Here we grab all forms ever submitted to this domain on CommCare HQ or all forms that the Applications
        for this domain know about.

        This fails after a couple hundred million forms are submitted to the domain.
        After that happens we'll just display a warning
        """
        try:
            form_buckets = get_all_xmlns_app_id_pairs_submitted_to_in_domain(self.domain)
        except ESError:
            self._all_form_retrieval_failed = True
            form_buckets = []

        all_submitted = {self.make_xmlns_app_key(xmlns, app_id)
                         for xmlns, app_id in form_buckets}
        from_apps = set(self._application_forms)
        return list(all_submitted.union(from_apps))

    @property
    @memoized
    def _application_forms(self):
        """
        These are forms with an xmlns that can be matched to an Application or Application-Deleted
        id with certainty.
        """
        data = self._get_all_forms_grouped_by_app_and_xmlns()
        return [self.make_xmlns_app_key(d.xmlns, d.app_id) for d in data]

    @property
    @memoized
    def _application_forms_info(self):
        """
            This is the data used for creating the drilldown_map. This returns the following type of structure:
            {
                'app_id': {
                    'app': {
                        'names': [<foo>] or '<foo>',
                        'id': '<foo>',
                        'langs': [<foo>]
                    },
                    'is_user_registration': (True or False),
                    'is_deleted': (True or False),
                    'modules' : [
                        {
                            'module': {
                                'names': [<foo>] or '<foo>',
                                'id': index,
                                'forms': [
                                    {
                                        'form': {
                                            'names': [<foo>] or '<foo>',
                                            'xmlns': <xmlns>
                                        }
                                ]
                            }
                        },
                        {...}
                    ]
                },
                'next_app_id': {...},
            }
        """
        data = get_all_form_details(self.domain)
        default_module = lambda num: {'module': None, 'forms': []}  # noqa: E731
        app_forms = {}
        for app_structure in data:
            index_offset = 1 if app_structure.is_user_registration else 0
            app_id = app_structure.app.id
            if app_id not in app_forms:
                app_forms[app_id] = {
                    'app': app_structure.app,
                    'is_user_registration': app_structure.is_user_registration,
                    'is_deleted': app_structure.is_deleted,
                    'modules': []
                }

            module_id = app_structure.module.id + index_offset

            new_modules = module_id - len(app_forms[app_id]['modules']) + 1
            if new_modules > 0:
                # takes care of filler modules (modules in the app with no form submissions.
                # these 'filler modules' are eventually ignored when rendering the drilldown map.
                app_forms[app_id]['modules'].extend([default_module(module_id - m) for m in range(0, new_modules)])

            if not app_structure.is_user_registration:
                app_forms[app_id]['modules'][module_id]['module'] = app_structure.module
                app_forms[app_id]['modules'][module_id]['forms'].append({
                    'form': app_structure.form,
                    'xmlns': app_structure.xmlns,
                })
        return app_forms

    @property
    @memoized
    def _nonmatching_app_forms(self):
        """
        These are forms that we could not find exact matches for in known or deleted apps
        (including remote apps)
        """
        all_forms = set(self._all_forms)
        std_app_forms = set(self._application_forms)
        nonmatching = all_forms.difference(std_app_forms)
        return list(nonmatching)

    @property
    @memoized
    def _fuzzy_forms(self):
        matches = {}
        app_data = self._get_all_forms_grouped_by_app_and_xmlns()
        app_xmlns = [d.xmlns for d in app_data]
        for form in self._nonmatching_app_forms:
            xmlns = self.split_xmlns_app_key(form, only_xmlns=True)
            if xmlns in app_xmlns:
                matches[form] = {
                    'app_ids': [d.app_id for d in app_data if d.xmlns == xmlns],
                    'xmlns': xmlns,
                }
        return matches

    @property
    @memoized
    def _fuzzy_form_data(self):
        fuzzy = {}
        for form in self._fuzzy_forms:
            xmlns, unknown_id = self.split_xmlns_app_key(form)
            fuzzy[xmlns] = {
                'apps': [detail for detail in get_form_details_for_xmlns(self.domain, xmlns)],
                'unknown_id': unknown_id,
            }
        return fuzzy

    @property
    def _hide_fuzzy_results(self):
        return self.request.GET.get('%s_%s' % (self.slug, self.fuzzy_slug)) == 'yes'

    @property
    @memoized
    def _unknown_forms(self):
        unknown = set(self._nonmatching_app_forms)
        if self._hide_fuzzy_results:
            fuzzy_forms = set(self._fuzzy_forms)
            unknown = list(unknown.difference(fuzzy_forms))
        return [u for u in unknown if u is not None]

    @property
    @memoized
    def _unknown_xmlns(self):
        return list(set([self.split_xmlns_app_key(x, only_xmlns=True) for x in self._unknown_forms]))

    @property
    def _show_unknown(self):
        return self.request.GET.get('%s_%s' % (self.slug, self.unknown_slug))

    @property
    @memoized
    def _unknown_forms_options(self):
        return [dict(val=x, text="%s; ID: %s" % (self.get_unknown_form_name(x), x)) for x in self._unknown_xmlns]

    @property
    def _selected_unknown_xmlns(self):
        if self._show_unknown:
            return self.request.GET.get('%s_%s_xmlns' % (self.slug, self.unknown_slug), '')
        return ''

    @memoized
    def get_unknown_form_name(self, xmlns, app_id=None, none_if_not_found=False):
        if app_id is not None and app_id != MISSING_APP_ID:
            try:
                app = Application.get_db().get(app_id)
            except ResourceNotFound:
                # must have been a weird app id, don't fail hard
                pass
            else:
                for module in app.get('modules', []):
                    for form in module['forms']:
                        if form['xmlns'] == xmlns:
                            return list(form['name'].values())[0]

        guessed_name = guess_form_name_from_submissions_using_xmlns(self.domain, xmlns)
        if guessed_name:
            return guessed_name

        if xmlns in SYSTEM_FORM_XMLNS_MAP:
            return SYSTEM_FORM_XMLNS_MAP[xmlns]

        return None if none_if_not_found else _("Name Unknown")

    @staticmethod
    def get_translated_value(display_lang, app_langs, obj):
        """
        Given a list of lang codes and a dictionary of lang codes to strings, output
        the value of the current display lang or the first lang available.

        If obj is a string, just output that string.
        """
        if isinstance(obj, str):
            return obj
        if not obj:
            return _('Untitled')

        val = obj.get(display_lang)
        if val:
            return val
        for lang in app_langs:
            val = obj.get(lang)
            if val:
                return val
        return obj.get(list(obj)[0], _('Untitled'))

    @staticmethod
    def _formatted_name_from_app(display_lang, app):
        langs = app['app']['langs']
        app_name = FormsByApplicationFilter.get_translated_value(display_lang, langs, app['app']['names'])
        module_name = FormsByApplicationFilter.get_translated_value(display_lang, langs, app['module']['names'])
        form_name = FormsByApplicationFilter.get_translated_value(display_lang, langs, app['form']['names'])
        is_deleted = app['is_deleted']
        if is_deleted:
            app_name = "%s [Deleted]" % app_name
        return "%s > %s > %s" % (app_name, module_name, form_name)

    @classmethod
    def has_selections(cls, request):
        params, instance = super(cls, cls).get_value(request, request.domain)
        if instance._show_unknown:
            return True
        for param in params:
            if param['slug'] == PARAM_SLUG_APP_ID:
                return True
        if request.GET.get('show_advanced') == 'on':
            return True
        return False

    def _get_filtered_data(self, filter_results):
        """
        Returns the raw form data based on the current filter selection.
        """
        if not filter_results:
            if self._application_forms:
                return get_all_form_details(self.domain)
            else:
                return []

        parsed_params = FormsByApplicationFilterParams(filter_results)
        if parsed_params.xmlns:
            return get_form_details_for_app_and_xmlns(
                self.domain,
                parsed_params.app_id,
                parsed_params.xmlns,
                deleted=parsed_params.status == PARAM_VALUE_STATUS_DELETED,
            )
        else:
            if not self._application_forms:
                return []
            return self.get_filtered_data_for_parsed_params(
                self.domain, parsed_params
            )

    @staticmethod
    def get_filtered_data_for_parsed_params(domain, parsed_params):
        # this code path has multiple forks:
        # 1. if status is set, but nothing else is, it will return all forms in apps of that status
        # 2. if status and app_id are set, but nothing else, it will return all forms in that app
        # 3. if status and app_id and module_id are set, it will return all forms in that module if
        #    the module is valid, otherwise it falls back to the app
        deleted = parsed_params.status == PARAM_VALUE_STATUS_DELETED
        if parsed_params.most_granular_filter == 'module':
            return get_form_details_for_app_and_module(
                domain, parsed_params.app_id, parsed_params.get_module_int(), deleted=deleted
            )
        elif parsed_params.most_granular_filter == 'app_id':
            return get_form_details_for_app(domain, parsed_params.app_id, deleted=deleted)
        elif parsed_params.most_granular_filter == 'status':
            return get_all_form_details(domain, deleted=deleted)

    def _get_selected_forms(self, filter_results):
        """
        Returns the appropriate form information based on the current filter selection.
        """
        if self._show_unknown:
            return self._get_selected_forms_for_unknown_apps()
        else:
            result = {}
            data = self._get_filtered_data(filter_results)
            for form_details in data:
                xmlns_app = self.make_xmlns_app_key(form_details.xmlns, form_details.app.id)
                if xmlns_app not in result:
                    result[xmlns_app] = self._generate_report_app_info(
                        form_details.xmlns,
                        form_details.app.id,
                        self._formatted_name_from_app(self.display_lang, form_details),
                    )

            if not self._hide_fuzzy_results and self._fuzzy_forms:
                selected_xmlns = [r['xmlns'] for r in result.values()]
                selected_apps = [r['app_id'] for r in result.values()]
                for xmlns, info in self._fuzzy_form_data.items():
                    for form_details in info['apps']:
                        if xmlns in selected_xmlns and form_details.app.id in selected_apps:
                            result["%s %s" % (xmlns, self.fuzzy_slug)] = self._generate_report_app_info(
                                xmlns,
                                info['unknown_id'],
                                "%s [Fuzzy Submissions]" % self._formatted_name_from_app(
                                    self.display_lang, form_details),
                                is_fuzzy=True,
                            )
            return result

    @staticmethod
    def _generate_report_app_info(xmlns, app_id, name, is_fuzzy=False):
        return {
            'xmlns': xmlns,
            'app_id': app_id,
            'name': name,
            'is_fuzzy': is_fuzzy,
        }

    def _get_selected_forms_for_unknown_apps(self):
        result = {}
        all_unknown = [self._selected_unknown_xmlns] if self._selected_unknown_xmlns else self._unknown_forms
        for form in all_unknown:
            xmlns, app_id = self.split_xmlns_app_key(form)
            if form not in result:
                result[xmlns] = self._generate_report_app_info(
                    xmlns,
                    None if self._selected_unknown_xmlns else app_id,
                    "%s; ID: %s" % (self.get_unknown_form_name(xmlns), xmlns)
                )
        return result

    @memoized
    def _get_all_forms_grouped_by_app_and_xmlns(self):
        return get_all_form_definitions_grouped_by_app_and_xmlns(self.domain)

    @classmethod
    def make_xmlns_app_key(cls, xmlns, app_id):
        """
            Uniquely identify a form with an xmlns+app_id pairing so that we can split fuzzy-matched data from
            non-fuzzy data.
        """
        if app_id == MISSING_APP_ID:
            return xmlns
        return "%s %s" % (xmlns, app_id)

    @classmethod
    def split_xmlns_app_key(cls, key, only_xmlns=False):
        """
            Takes an unique xmlns+app_id key generated by make_xmlns_app_key and spits out the xmlns and app_id.
        """
        if key is None:
            return key
        identify = key.split(' ')
        xmlns = identify[0]
        if only_xmlns:
            return xmlns
        app_id = identify[1] if len(identify) > 1 else MISSING_APP_ID
        return xmlns, app_id

    @classmethod
    def get_labels(cls):
        return [
            (_('Application'),
             _("Select an Application") if cls.use_only_last
             else _("Show Forms in all Applications"), PARAM_SLUG_APP_ID),
            (_('Menu'),
             _("Select a Menu") if cls.use_only_last
             else _("Show all Forms in selected Application"), PARAM_SLUG_MODULE),
            (_('Form'),
             _("Select a Form") if cls.use_only_last
             else _("Show all Forms in selected Module"), PARAM_SLUG_XMLNS),
        ]

    @classmethod
    def get_value(cls, request, domain):
        """
            Gets the value of this filter---to be used by the relevant report.
        """
        filter_results, instance = super(FormsByApplicationFilter, cls).get_value(request, domain)
        return instance._get_selected_forms(filter_results)


class SingleFormByApplicationFilter(FormsByApplicationFilter):
    """
        Same as its superclass, except you _must_ select one form by the end of it.
    """
    label = gettext_noop("Choose a Form")
    use_only_last = True
    show_global_hide_fuzzy_checkbox = False


class CompletionOrSubmissionTimeFilter(BaseSingleOptionFilter):
    slug = "sub_time"
    label = gettext_lazy("Filter Dates By")
    css_class = "span2"
    default_text = gettext_lazy("Completion Time")

    def _generate_help_message():
        completion_help = mark_safe_lazy(gettext_lazy(  # nosec: no user input
            "<strong>Completion</strong> time is when the form is completed on the phone."))

        submission_help = mark_safe_lazy(gettext_lazy(  # nosec: no user input
            "<strong>Submission</strong> time is when {hq_name} receives the form.".format(
                hq_name=commcare_hq_names()['commcare_hq_names']['COMMCARE_HQ_NAME'])))

        return format_html_lazy("{}<br />{}", completion_help, submission_help)

    help_text = _generate_help_message()

    @property
    def options(self):
        return [
            ('submission', _('Submission Time')),
        ]
