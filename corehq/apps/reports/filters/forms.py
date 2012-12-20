from couchdbkit.schema.properties import LazyDict
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter, BaseSingleOptionFilter
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized
from settings import REMOTE_APP_NAMESPACE

# For translations
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop


class FormsByApplicationFilter(BaseDrilldownOptionFilter):
    """
        Use this filter to drill down by
        (Active Applications or Deleted Applications or Remote Applications >) Application > Module > Form

        You may also select Unknown Forms for forms that can't be matched to any known Application, Application-Deleted,
        RemoteApp, or RemoteApp-Deleted for this domain.

        You may also hide/show fuzzy results (where fuzzy means you can't match that XMLNS to exactly one Application
        or Application-Deleted).
    """
    slug = "form"
    label = ugettext_noop("Filter Forms")
    css_class = "span5"
    drilldown_empty_text = ugettext_noop("You don't have any applications set up, so there are no forms "
                                            "to choose from. Please create an application!")
    template = "reports/filters/form_app_module_drilldown.html"
    unknown_slug = "unknown"
    fuzzy_slug = "@@FUZZY"
    show_global_hide_fuzzy_checkbox = True
    unknown_remote_app_id = 'unknown_remote_app'

    @property
    def display_lang(self):
        """
            This should return the lang code of the language being used to view this form.
        """
        # todo make this functional
        return 'en'

    @property
    def final_notifications(self):
        """
            The notification that might pop up when you reach the last result of the drilldown.
        """
        notifications = {}
        for xmlns, info in self.fuzzy_form_data.items():
            app_map = info['apps']
            active = []
            deleted = []
            for app in app_map:
                formatted_name = self.formatted_name_from_app(app)
                if app['is_deleted']:
                    deleted.append(formatted_name)
                else:
                    active.append(formatted_name)

            if not deleted and len(active) == 1:
                continue

            notifications[xmlns] = render_to_string("reports/filters/partials/fuzzy_form_message.html", {
                'xmlns': xmlns,
                'active': active,
                'deleted': deleted,
                'good_news': len(active) == 1,
                'hide_fuzzy': {
                    'show': not self.show_global_hide_fuzzy_checkbox,
                    'slug': '%s_%s' % (self.slug, self.fuzzy_slug),
                    'checked': self.hide_fuzzy_results,
                }
            })
        return notifications

    @property
    def rendered_labels(self):
        """
            Here we determine whether to extend the drilldown to allow the user to choose application types.
            Current supported types are:
            - Active Application (Application)
            - Deleted Application (Application-Deleted)
            - Remote Application (RemoteApp and RemoteApp-Deleted)
        """
        labels = self.get_labels()
        if self.drilldown_map and self.drilldown_map[0]['val'] == 'active':
            labels = [
                 (_('Application Type'),
                  _("Select an Application Type") if self.use_only_last else _("Show all Application Types"),
                  'status'),
                 (_('Application'),
                  _("Select Application...") if self.use_only_last else _("Show all Forms of this Application Type..."),
                  'app_id'),
             ] + labels[1:]
        return labels

    @property
    def filter_context(self):
        context = super(FormsByApplicationFilter, self).filter_context
        context.update({
            'unknown_available': bool(self.unknown_forms),
            'unknown': {
                'show': self.show_unknown,
                'slug': self.unknown_slug,
                'selected': self.selected_unknown_xmlns,
                'options': self.unknown_forms_options,
                'default_text': "Select an Unknown Form..." if self.use_only_last else "Show All Unknown Forms..."
            },
            'hide_fuzzy': {
                'show': not self.show_unknown and self.show_global_hide_fuzzy_checkbox and self.fuzzy_forms,
                'slug': '%s_%s' % (self.slug, self.fuzzy_slug),
                'checked': self.hide_fuzzy_results,
            }
        })
        return context

    @property
    @memoized
    def drilldown_map(self):
        final_map = []
        map_active = []
        map_remote = []
        map_deleted = []

        all_forms = self.application_forms_info.copy()
        all_forms.update(self.remote_forms_info.copy())

        for app_map in all_forms.values():
            app_langs = app_map['app']['langs']
            is_deleted = app_map['is_deleted']
            is_remote = app_map.get('is_remote', False)

            app_name = self.get_translated_value(app_langs, app_map['app']['names'])
            if is_deleted:
                app_name = "%s [Deleted Application]" % app_name
            app = self._map_structure(app_map['app']['id'], app_name)

            for module_map in app_map['modules']:
                module_name = self.get_translated_value(app_langs, module_map['module']['names'])
                module = self._map_structure(module_map['module']['id'], module_name)
                for form_map in module_map['forms']:
                    form_name = self.get_translated_value(app_langs, form_map['form']['names'])
                    module['next'].append(self._map_structure(form_map['xmlns'], form_name))
                app['next'].append(module)

            if is_remote:
                map_remote.append(app)
            elif is_deleted:
                map_deleted.append(app)
            else:
                map_active.append(app)

        if (bool(map_remote) + bool(map_deleted) + bool(map_active)) > 1:
            if map_active:
                final_map.append(self._map_structure('active', _('Active CommCare Applications'), map_active))
            if map_remote:
                final_map.append(self._map_structure('remote', _('Remote CommCare Applications'), map_remote))
            if map_deleted:
                final_map.append(self._map_structure('deleted', _('Deleted CommCare Applications'), map_deleted))
        else:
            final_map.extend(map_active or map_remote or map_deleted)

        return final_map

    @property
    @memoized
    def all_forms(self):
        """
            Here we grab all forms ever submitted to this domain on CommCare HQ or all forms that the Applications
            for this domain know about.
        """
        key = ["submission xmlns app", self.domain]
        data = get_db().view('reports_forms/all_forms',
            startkey=key,
            endkey=key+[{}],
            group=True,
            group_level=4,
        ).all()
        all_submitted = set(self.get_xmlns_app_keys(data))
        from_apps = set(self.application_forms)
        return list(all_submitted.union(from_apps))

    @property
    @memoized
    def application_forms(self):
        """
            These are forms with an xmlns that can be matched to an Application or Application-Deleted
            id with certainty.
        """
        data = self._raw_data(["xmlns app", self.domain], group=True)
        all_forms = self.get_xmlns_app_keys(data)
        return all_forms

    @property
    @memoized
    def application_forms_info(self):
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
        data = self._raw_data(["app module form", self.domain])
        app_forms = {}
        for line in data:
            app_info = line.get('value')
            if not app_info:
                continue

            index_offset = 1 if app_info.get('is_user_registration', False) else 0

            app_id = app_info['app']['id']

            if not app_id in app_forms:
                app_forms[app_id] = {
                    'app': app_info['app'],
                    'is_user_registration': app_info.get('is_user_registration', False),
                    'is_deleted': app_info['is_deleted'],
                    'modules': []
                }

            module_id = app_info['module']['id'] + index_offset
            if module_id+1 > len(app_forms[app_id]['modules']):
                app_forms[app_id]['modules'].append({
                    'module': app_info['module'],
                    'forms': [],
                })

            app_forms[app_id]['modules'][module_id]['forms'].append({
                'form': app_info['form'],
                'xmlns': app_info['xmlns'],
            })
        return app_forms

    @property
    @memoized
    def remote_forms(self):
        """
            These are forms with an xmlns that can be matched to a RemoteApp or RemoteApp-Deleted id or
            they have an xmlns which follows our remote app namespacing pattern.
        """
        result = {}

        all_forms = set(self.all_forms)
        std_app_forms = set(self.application_forms)
        other_forms = list(all_forms.difference(std_app_forms))

        remote_app_namespace = REMOTE_APP_NAMESPACE % {'domain': self.domain}

        key = ["", self.domain]
        remote_app_data = get_db().view('reports_apps/remote',
            reduce=False,
            startkey=key,
            endkey=key+[{}],
        ).all()
        remote_apps = dict([(d['id'], d['value']) for d in remote_app_data])


        for form in other_forms:
            if form:
                xmlns, app_id = self.split_xmlns_app_key(form)
                if app_id in remote_apps.keys() or remote_app_namespace in xmlns:
                    if app_id in remote_apps.keys():
                        app_info = remote_apps[app_id]
                    else:
                        app_info = {
                            'app': {
                                'is_unknown': True,
                                'id': self.unknown_remote_app_id,
                                'names': 'Name Unknown',
                                'langs': None,
                            },
                            'is_deleted': False,
                        }

                    # A little hokey, but for the RemoteApps that follow our expected namespacing we can lift
                    # the module and form names from the xmlns.
                    module_desc = xmlns.split('/')
                    form_name = self.get_unknown_form_name(xmlns, app_id=app_id if app_id else None, none_if_not_found=True)
                    if remote_app_namespace in xmlns:
                        module_name = module_desc[-2] if len(module_desc) > 1 else None
                        if not form_name:
                            form_name = module_desc[-1] if module_desc else None
                    else:
                        module_name = None

                    app_info.update({
                        'module': {
                            'names': module_name or "Unknown Module",
                            'id': module_name or "unknown_module",
                        },
                        'form': {
                            'names': form_name or "Unknown Name",
                            'id': form_name or 'unknown_form',
                        },
                        'xmlns': xmlns,
                    })
                    result[form] = app_info

        return result

    @property
    @memoized
    def remote_forms_info(self):
        """
            Used for placing remote forms into the drilldown_map. Outputs the same structure as application_forms_info.
        """
        remote_forms = {}
        for form, info in self.remote_forms.items():
            app_id = info['app']['id']
            if not app_id in remote_forms:
                module_names = sorted(set([d['module']['names'] for d in self.remote_forms.values()
                                       if d['app']['id'] == app_id]))
                remote_forms[app_id] = {
                    'app': info['app'],
                    'is_user_registration': False,
                    'is_remote': True,
                    'is_deleted': info['is_deleted'],
                    'module_names': module_names,
                    'modules': [None]*len(module_names)
                }

            module_index = remote_forms[app_id]['module_names'].index(info['module']['names'])
            if remote_forms[app_id]['modules'][module_index] is None:
                form_names = sorted(set([d['form']['names'] for d in self.remote_forms.values()
                                     if d['app']['id'] == app_id and d['module']['id'] == info['module']['id']]))
                remote_forms[app_id]['modules'][module_index] = {
                    'module': {
                        'names': info['module']['names'],
                        'id': module_index
                    },
                    'form_names': form_names,
                    'forms': [None]*len(form_names),
                }

            form_index = remote_forms[app_id]['modules'][module_index]['form_names'].index(info['form']['names'])
            remote_forms[app_id]['modules'][module_index]['forms'][form_index] = {
                'form': {
                    'names': info['form']['names'],
                    'id': form_index,
                },
                'xmlns': info['xmlns'],
            }
        return remote_forms

    @property
    @memoized
    def nonmatching_app_forms(self):
        """
            These are forms that we could not find exact matches for in remote apps or in

        """
        all_forms = set(self.all_forms)
        std_app_forms = set(self.application_forms)
        remote_app_forms = set(self.remote_forms.keys())
        nonmatching = all_forms.difference(std_app_forms)
        return list(nonmatching.difference(remote_app_forms))

    @property
    @memoized
    def fuzzy_forms(self):
        matches = {}
        app_data = self._raw_data(["xmlns app", self.domain], group=True)
        app_xmlns = [d['key'][-2] for d in app_data]
        for form in self.nonmatching_app_forms:
            xmlns = self.split_xmlns_app_key(form, only_xmlns=True)
            if xmlns in app_xmlns:
                matches[form] = {
                    'app_ids': [d['key'][-1] for d in app_data if d['key'][-2] == xmlns],
                    'xmlns': xmlns,
                    }
        return matches

    @property
    @memoized
    def fuzzy_xmlns(self):
        return [d['xmlns'] for d in self.fuzzy_forms.values()]

    @property
    @memoized
    def fuzzy_form_data(self):
        fuzzy = {}
        for form in self.fuzzy_forms:
            xmlns, unknown_id = self.split_xmlns_app_key(form)
            key = ["xmlns", self.domain, xmlns]
            info = self._raw_data(key)
            fuzzy[xmlns] = {
                'apps': [i['value'] for i in info],
                'unknown_id': unknown_id,
            }
        return fuzzy

    @property
    @memoized
    def hide_fuzzy_results(self):
        return self.request.GET.get('%s_%s' % (self.slug, self.fuzzy_slug)) == 'yes'

    @property
    @memoized
    def unknown_forms(self):
        nonmatching = set(self.nonmatching_app_forms)
        fuzzy_forms = set(self.fuzzy_forms.keys())

        unknown = list(nonmatching.difference(fuzzy_forms))
        return [u for u in unknown if u is not None]

    @property
    @memoized
    def unknown_xmlns(self):
        return list(set([self.split_xmlns_app_key(x, only_xmlns=True) for x in self.unknown_forms]))

    @property
    def show_unknown(self):
        return self.request.GET.get('%s_%s' % (self.slug, self.unknown_slug))

    @property
    @memoized
    def unknown_forms_options(self):
        return [dict(val=x, text="%s; ID: %s" % (self.get_unknown_form_name(x), x)) for x in self.unknown_xmlns]

    @property
    @memoized
    def selected_unknown_xmlns(self):
        if self.show_unknown:
            return self.request.GET.get('%s_%s_xmlns' % (self.slug, self.unknown_slug), '')
        return ''

    def formatted_name_from_app(self, app):
        langs = app['app']['langs']
        app_name = self.get_translated_value(langs, app['app']['names'])
        module_name = self.get_translated_value(langs, app['module']['names'])
        form_name = self.get_translated_value(langs, app['form']['names'])
        is_deleted = app.get('is_deleted', False)
        if is_deleted:
            app_name = "%s [Deleted]" % app_name
        return "%s > %s > %s" % (app_name, module_name, form_name)

    @memoized
    def get_unknown_form_name(self, xmlns, app_id=None, none_if_not_found=False):
        key = ["xmlns", self.domain, xmlns]
        if app_id is not None:
            key[0] = "xmlns app"
            key.append(app_id)
        data = get_db().view('reports_forms/name_by_xmlns',
            reduce=False,
            startkey=key,
            endkey=key+[{}],
            limit=1,
        ).first()
        if data:
            return data['value']
        return None if none_if_not_found else "Name Unknown"

    def get_translated_value(self, app_langs, obj):
        """
            Given a list of lang codes and a dictionary of lang codes to strings, output
            the value of the current display lang or the first lang available.

            If obj is a string, just output that string.
        """
        if isinstance(obj, basestring):
            return obj
        val = obj.get(self.display_lang)
        if val:
            return val
        for lang in app_langs:
            val = obj.get(lang)
            if val:
                return val
        return obj.get(obj.keys()[0], _('Untitled'))

    def get_filtered_data(self, filter_results):
        """
            Returns the raw form data based on the current filter selection.
        """
        if not filter_results:
            data = []
            if self.application_forms:
                key = ["app module form", self.domain]
                data.extend(self._raw_data(key))
            if self.remote_forms:
                data.extend([{'value': v} for v in self.remote_forms.values()])
            return data

        use_remote_form_data = bool((filter_results[0]['slug'] == 'status' and filter_results[0]['value'] == 'remote') or
                                (filter_results[0]['slug'] == 'app' and self.remote_forms))

        if filter_results[-1]['slug'] == 'xmlns':
            xmlns = filter_results[-1]['value']
            app_id = filter_results[-3]['value']
            if use_remote_form_data:
                app_id = app_id if app_id != self.unknown_remote_app_id else {}
                data = [{'value': self.remote_forms[self.make_xmlns_app_key(xmlns, app_id)]}]
            else:
                status = filter_results[0]['value'] if filter_results[0]['slug'] == 'status' else 'active'
                key = ["status xmlns app", self.domain, status, filter_results[-1]['value'], filter_results[-3]['value']]
                data = self._raw_data(key)
        else:
            data = []

            if use_remote_form_data:
                all_forms = []
                if filter_results[-1]['slug'] == 'module':
                    app_id = filter_results[-2]['value']
                    try:
                        module_id = int(filter_results[-1]['value'])
                        all_forms.extend(self.remote_forms_info[app_id]['modules'][module_id]['forms'])
                    except (KeyError, ValueError):
                        pass
                else:
                    app_id = filter_results[-1]['value']
                    try:
                        for module in self.remote_forms_info[app_id]['modules']:
                            all_forms.extend(module['forms'])
                    except KeyError:
                        pass
                app_id = app_id if app_id != self.unknown_remote_app_id else {}
                data.extend([{'value': self.remote_forms[self.make_xmlns_app_key(f['xmlns'], app_id)]} for f in all_forms])

            if (self.application_forms and
                not (filter_results[0]['slug'] == 'status' and filter_results[0]['value'] == 'remote')):
                prefix = "app module form"
                key = [self.domain]
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
                data.extend(self._raw_data([prefix]+key))
        return data

    def get_selected_forms(self, filter_results):
        """
            Returns the appropriate form information based on the current filter selection.
        """
        def _generate_report_app_info(xmlns, app_id, name, is_fuzzy=False, is_remote=False):
            return {
                'xmlns': xmlns,
                'app_id': app_id,
                'name': name,
                'is_fuzzy': is_fuzzy,
                'is_remote': is_remote
            }

        result = {}
        if self.show_unknown:
            all_unknown = [self.selected_unknown_xmlns] if self.selected_unknown_xmlns else self.unknown_forms
            for form in all_unknown:
                xmlns, app_id = self.split_xmlns_app_key(form)
                if form not in result:
                    result[xmlns] = _generate_report_app_info(
                        xmlns,
                        None if self.selected_unknown_xmlns else app_id,
                        "%s; ID: %s" % (self.get_unknown_form_name(xmlns), xmlns)
                    )
        else:
            data = self.get_filtered_data(filter_results)
            for line in data:
                app = line['value']
                app_id = app['app']['id']
                app_id = app_id if app_id != self.unknown_remote_app_id else {}
                xmlns_app = self.make_xmlns_app_key(app['xmlns'], app_id)
                if xmlns_app not in result:
                    result[xmlns_app] = _generate_report_app_info(
                        app['xmlns'],
                        app_id,
                        self.formatted_name_from_app(app),
                        is_remote=app.get('is_remote', False),
                    )

            if self.fuzzy_forms and not self.hide_fuzzy_results:
                selected_xmlns = [r['xmlns'] for r in result.values()]
                selected_apps = [r['app_id'] for r in result.values()]
                for xmlns, info in self.fuzzy_form_data.items():
                    for app_map in info['apps']:
                        if xmlns in selected_xmlns and app_map['app']['id'] in selected_apps:
                            result["%s %s" % (xmlns, self.fuzzy_slug)] = _generate_report_app_info(
                                xmlns,
                                info['unknown_id'],
                                "%s [Fuzzy Submissions]" % self.formatted_name_from_app(app_map),
                                is_fuzzy=True,
                            )
        return result

    def _raw_data(self, startkey, endkey=None, reduce=False, group=False):
        if endkey is None:
            endkey = startkey
        kwargs = dict(group=group) if group else dict(reduce=reduce)
        return get_db().view('reports_forms/by_app_info',
            startkey=startkey,
            endkey=endkey+[{}],
            **kwargs
        ).all()

    @classmethod
    def get_xmlns_app_keys(cls, data):
        return [cls.make_xmlns_app_key(d['key'][-2], d['key'][-1]) for d in data]

    @classmethod
    def make_xmlns_app_key(cls, xmlns, app_id):
        """
            Uniquely identify a form with an xmlns+app_id pairing so that we can split fuzzy-matched data from
            non-fuzzy data.
        """
        if isinstance(app_id, dict) or isinstance(app_id, LazyDict):
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
        app_id = identify[1] if len(identify) > 1 else {}
        return xmlns, app_id

    @classmethod
    def get_labels(cls):
        return [
            (_('Application'), _("Select an Application") if cls.use_only_last
                                    else _("Show Forms in all Applications"), 'app'),
            (_('Module'), _("Select a Module") if cls.use_only_last
                                    else _("Show Forms from all Modules in selected Application"), 'module'),
            (_('Form'), _("Select a Form") if cls.use_only_last
                                    else _("Show all Forms in selected Module"), 'xmlns'),
        ]

    @classmethod
    def get_value(cls, request, domain):
        """
            Gets the value of this filter---to be used by the relevant report.
        """
        filter_results, instance = super(FormsByApplicationFilter, cls).get_value(request, domain)
        return instance.get_selected_forms(filter_results)


class SingleFormByApplicationFilter(FormsByApplicationFilter):
    """
        Same as its superclass, except you _must_ select one form by the end of it.
    """
    label = ugettext_noop("Choose a Form")
    use_only_last = True
    show_global_hide_fuzzy_checkbox = False

    def get_selected_forms(self, filter_results):
        xmlns = None
        app_id = None
        if self.show_unknown and self.selected_unknown_xmlns:
            xmlns = self.selected_unknown_xmlns
        elif filter_results and filter_results[-1]['slug'] == 'xmlns':
            xmlns = filter_results[-1]['value']
            if self.fuzzy_forms and self.hide_fuzzy_results:
                app_id = filter_results[-3]['value']
            app_id = app_id if app_id != self.unknown_remote_app_id else {}
        return {
            'xmlns': xmlns,
            'app_id': app_id,
        }


class CompletionOrSubmissionTimeFilter(BaseSingleOptionFilter):
    slug = "sub_time"
    label = ugettext_noop("Filter Dates By")
    css_class = "span2"
    help_text = mark_safe("%s<br />%s" % (ugettext_noop("<strong>Completion</strong> time is when the form is completed on the phone."),
                                          ugettext_noop("<strong>Submission</strong> time is when CommCare HQ receives the form.")))
    default_text = ugettext_noop("Completion Time")

    @property
    def options(self):
        return [
            ('submission', _('Submission Time')),
        ]
