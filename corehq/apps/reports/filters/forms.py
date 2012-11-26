from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter, BaseSingleOptionFilter
from corehq.apps.reports.util import all_xmlns_in_domain, all_application_forms, get_app_xmlns
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized

# For translations
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop


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
        return get_app_xmlns(self.domain, duplicates_only=True)

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
        for xmlns, app_map in self.duplicate_form_info.items():
            active_dupes = []
            deleted_dupes = []
            for app in app_map:
                formatted_name = self.formatted_name_from_app(app)
                if app['is_deleted']:
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
                (_('Form Type'), _("Select a Form Type") if self.use_only_last else _("Show all Forms"), 'status'),
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

        app_form_map, app_xmlns = all_application_forms(self.domain)
        deleted_xmlns = self._get_deleted_xmlns(self.domain, app_xmlns)

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

    def formatted_name_from_app(self, app):
        langs = app['app']['langs']
        app_name = self._get_lang_value(langs, app['app']['names'])
        module_name = self._get_lang_value(langs, app['module']['names'])
        form_name = self._get_lang_value(langs, app['form']['names'])
        is_deleted = app.get('is_deleted', False)
        if is_deleted:
            app_name = "%s [Deleted]" % app_name
        return "%s > %s > %s" % (app_name, module_name, form_name)

    @memoized
    def _get_lang_value(self, app_langs, obj):
        if isinstance(obj, basestring):
            return obj
        for lang in app_langs:
            val = obj.get(self.display_lang or lang)
            if val:
                return val
        return obj.get(obj.keys()[0], _('Untitled'))

    @staticmethod
    def _get_deleted_xmlns(domain, app_xmlns):
        all_xmlns = set(all_xmlns_in_domain(domain))
        app_xmlns = set(app_xmlns)
        return list(all_xmlns.difference(app_xmlns))

    @classmethod
    def labels(cls):
        return [
            (_('Application'), _("Select an Application") if cls.use_only_last else _("Show Forms in all Applications"), 'app'),
            (_('Module'), _("Select a Module") if cls.use_only_last else _("Show Forms from all Modules in selected Application"), 'module'),
            (_('Form'), _("Select a Form") if cls.use_only_last else _("Show all Forms in selected Module"), 'xmlns'),
        ]

    @classmethod
    def _get_vals_from_map(cls, map, keys):
        current_key = keys[0].get('value')
        vals = map.get(current_key)
        if len(keys) == 1:
            return vals
        return cls._get_vals_from_map(vals, keys[1:])

    @classmethod
    def _get_data(cls, startkey, endkey=None):
        if endkey is None:
            endkey = startkey
        return get_db().view('reports_forms/by_app_info',
            reduce=False,
            startkey=startkey,
            endkey=endkey+[{}],
        ).all()

    @classmethod
    def get_filtered_data(cls, domain, filter_results):
        include_deleted = False
        if not filter_results:
            key = ["status app module form", domain]
            data = cls._get_data(key+["active"], key+["deleted"])
            include_deleted = True
        elif filter_results[-1]['slug'] == 'xmlns':
            status = filter_results[0]['value'] if filter_results[0]['slug'] == 'status' else 'active'
            key = ["status xmlns", domain, status, filter_results[-1]['value']]
            data = cls._get_data(key)
        else:
            if (filter_results[0]['slug'] == 'status' and filter_results[0]['value'] == 'deleted'
                and (len(filter_results) == 1 or filter_results[1]['value'] == 'app_unknown')):
                include_deleted = True
            prefix = "app module form"
            key = [domain]
            if filter_results[0]['slug'] == 'status':
                prefix = "%s %s" % ("status", prefix)
            for f in filter_results:
                val = f['value']
                if f['slug'] == 'module':
                    try:
                        val = int(val)
                    except Exception:
                        break
                key.append(val)
            data = cls._get_data([prefix]+key)
        return data, include_deleted

    @classmethod
    def get_all_xmlns(cls, request, domain):
        filtered_xmlns = {}
        filter_results, instance = cls.get_value(request, domain)
        data, include_deleted = cls.get_filtered_data(domain, filter_results)
        if include_deleted:
            app_xmlns = get_app_xmlns(domain)
            all_deleted = cls._get_deleted_xmlns(domain, app_xmlns)
            filtered_xmlns.update(dict([(d, dict(name="%s [Deleted Form]" % d, is_dupe=False)) for d in all_deleted]))
        for line in data:
            app = line['value']
            if app['xmlns'] not in filtered_xmlns:
                filtered_xmlns[app['xmlns']] = {
                    'name': instance.formatted_name_from_app(app),
                    'is_dupe': bool(app['xmlns'] in instance.duplicate_xmlns),
                }
        return filtered_xmlns


class SingleFormByApplicationFilter(FormsByApplicationFilter):
    label = ugettext_noop("Choose a Form")
    use_only_last = True

    @classmethod
    def get_value(cls, request, domain):
        selected_form, _instance = super(SingleFormByApplicationFilter, cls).get_value(request, domain)
        if selected_form and selected_form[-1]['slug'] == 'xmlns':
            return selected_form[-1]['value']
        return None


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