from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from corehq.apps.reports.display import FormType
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter, BaseSingleOptionFilter
# For translations
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from corehq.apps.reports.util import all_xmlns_in_domain, all_application_forms, get_duplicate_xmlns
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized


class FormsByApplicationFilter(BaseDrilldownOptionFilter):
    slug = "form"
    label = ugettext_noop("Filter Forms")
    css_class = "span5"

    @property
    def display_lang(self):
        # todo make this functional
        return 'en'

    @property
    @memoized
    def duplicate_xmlns(self):
        return get_duplicate_xmlns(self.domain)

    @property
    @memoized
    def duplicate_form_info(self):
        dupes = {}
        for xmlns in self.duplicate_xmlns:
            key = ["xmlns", self.domain, xmlns]
            info = get_db().view('reports_forms/by_app_info',
                reduce=False,
                startkey=key,
                endkey=key+[{}]
            ).all()
            dupes[xmlns] = [i['value'] for i in info]
        return dupes

    @property
    def final_notifications(self):
        notifications = {}
        show_deleted_message = False
        for xmlns, app_map in self.duplicate_form_info.items():
            active_dupes = []
            deleted_dupes = []
            for app in app_map:
                langs = app['app']['langs']
                app_name = self._get_lang_value(langs, app['app']['names'])
                module_name = self._get_lang_value(langs, app['module']['names'])
                form_name = self._get_lang_value(langs, app['form']['names'])
                is_deleted = app.get('is_deleted', False)
                if is_deleted:
                    app_name = "%s [Deleted]" % app_name
                formatted_name = "%s > %s > %s" % (app_name, module_name, form_name)
                if is_deleted:
                    deleted_dupes.append(formatted_name)
                else:
                    active_dupes.append(formatted_name)

            notifications[xmlns] = render_to_string("reports/filters/partials/duplicate_form_message.html", {
                'xmlns': xmlns,
                'active_dupes': active_dupes,
                'deleted_dupes': deleted_dupes,
                'good_news': len(active_dupes) == 1,
            })
        return notifications

    @property
    def rendered_labels(self):
        labels = self.labels()
        if self.drilldown_map and self.drilldown_map[0].get('val') == 'active':
            labels = [
                (_('Form Type'), _("Select a Form Type") if self.use_only_last else _("Show all Forms"), 'type'),
                (_('Application'),
                 _("Select...") if self.use_only_last else _("Show all Forms of this type..."),
                 'app_id'),
            ] + labels[1:]
        return labels

    @property
    @memoized
    def drilldown_map(self):
        final_map = []
        map_active = []
        map_deleted = []

        all_xmlns = set(all_xmlns_in_domain(self.domain))
        app_form_map, app_xmlns = all_application_forms(self.domain)

        app_xmlns = set(app_xmlns)
        deleted_xmlns = list(all_xmlns.difference(app_xmlns))

        deleted_forms = [self._map_structure(x, "Name Unknown; ID: %s" % x) for x in deleted_xmlns]
        if deleted_forms:
            deleted_forms_map = self._map_structure(_('app_unknown'), _('Unknown Application [Deleted Forms]'),
                [self._map_structure(_('module_unknown'), _('Unknown Module [Deleted Forms]'), deleted_forms)]
            )
            map_deleted.append(deleted_forms_map)


        for app_map in app_form_map.values():
            app_langs = app_map['app']['langs']
            is_deleted = app_map['is_deleted']

            app_name = self._get_lang_value(app_langs, app_map['app']['names'])
            if is_deleted:
                app_name = "%s [Deleted Application]" % app_name
            app = self._map_structure(app_map['app']['id'], app_name)

            for module_map in app_map['modules']:
                module_name = self._get_lang_value(app_langs, module_map['module']['names'])
                module = self._map_structure(module_map['module']['id'], module_name)
                for form_map in module_map['forms']:
                    form_name = self._get_lang_value(app_langs, form_map['form']['names'])
                    module['next'].append(self._map_structure(form_map['xmlns'], form_name))
                app['next'].append(module)

            if is_deleted:
                map_deleted.append(app)
            else:
                map_active.append(app)

        if map_deleted:
            final_map.append(self._map_structure('active', _('Forms in Applications'), map_active))
            final_map.append(self._map_structure('deleted', _('Deleted Forms or Forms from Deleted Applications'), map_deleted))
        else:
            final_map.extend(map_active)

        return final_map

    @memoized
    def _get_lang_value(self, app_langs, obj):
        if isinstance(obj, basestring):
            return obj
        for lang in app_langs:
            val = obj.get(self.display_lang or lang)
            if val:
                return val
        return obj.get(obj.keys()[0], _('Untitled'))

    @classmethod
    def labels(cls):
        return [
            (_('Application'), _("Select an Application") if cls.use_only_last else _("Show Forms in all Applications"), 'app_id'),
            (_('Module'), _("Select a Module") if cls.use_only_last else _("Show Forms from all Modules in selected Application"), 'module_id'),
            (_('Form'), _("Select a Form") if cls.use_only_last else _("Show all Forms in selected Module"), 'xmlns'),
        ]


class CompletionOrSubmissionTimeFilter(BaseSingleOptionFilter):
    slug = "sub_time"
    label = ugettext_noop("Filter Dates By")
    css_class = "span2"
    help_text = mark_safe("%s<br />%s" % (ugettext_noop("<strong>Completion</strong> time is when the form is completed on the phone."),
                                          ugettext_noop("<strong>Submission</strong> time is when we receive the form.")))
    default_text = ugettext_noop("Completion Time")


    @property
    def options(self):
        return [
            ('submission', _('Submission Time')),
        ]