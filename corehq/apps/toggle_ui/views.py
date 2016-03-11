import json
from collections import Counter
from couchdbkit.exceptions import ResourceNotFound
from django.core.urlresolvers import reverse
from django.http.response import Http404, HttpResponse
from django.utils.decorators import method_decorator
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_js_domain_cachebuster, \
    toggle_js_user_cachebuster
from couchforms.analytics import get_last_form_submission_received
from corehq.apps.domain.models import Domain
from corehq.apps.domain.decorators import require_superuser_or_developer
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.users.models import CouchUser
from corehq.apps.style.decorators import use_bootstrap3, use_datatables
from corehq.toggles import all_toggles, ALL_TAGS, NAMESPACE_USER, NAMESPACE_DOMAIN
from toggle.models import Toggle
from toggle.shortcuts import clear_toggle_cache

NOT_FOUND = "Not Found"


class ToggleBaseView(BasePageView):

    @method_decorator(require_superuser_or_developer)
    @use_bootstrap3
    def dispatch(self, request, *args, **kwargs):
        return super(ToggleBaseView, self).dispatch(request, *args, **kwargs)

    def toggle_map(self):
        return dict([(t.slug, t) for t in all_toggles()])


class ToggleListView(ToggleBaseView):
    urlname = 'toggle_list'
    page_title = "Feature Flags"
    template_name = 'toggle/flags.html'

    @use_datatables
    def dispatch(self, request, *args, **kwargs):
        return super(ToggleListView, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def show_usage(self):
        return self.request.GET.get('show_usage') == 'true'

    @property
    def page_context(self):
        toggles = list(all_toggles())
        domain_counts = {}
        active_domain_count = {}
        user_counts = {}
        last_used = {}
        last_modified = {}
        if self.show_usage:
            for t in toggles:
                counter = Counter()
                try:
                    usage = Toggle.get(t.slug)
                except ResourceNotFound:
                    domain_counts[t.slug] = 0
                    user_counts[t.slug] = 0
                    active_domain_count[t.slug] = 0
                else:
                    for u in usage.enabled_users:
                        namespace = u.split(":", 1)[0] if u.find(":") != -1 else NAMESPACE_USER
                        counter[namespace] += 1
                    usage_info = _get_usage_info(usage)
                    domain_counts[t.slug] = counter.get(NAMESPACE_DOMAIN, 0)
                    active_domain_count[t.slug] = usage_info["_active_domains"]
                    user_counts[t.slug] = counter.get(NAMESPACE_USER, 0)
                    last_used[t.slug] = usage_info["_latest"]
                    last_modified[t.slug] = usage.last_modified
        return {
            'domain_counts': domain_counts,
            'active_domain_count': active_domain_count,
            'page_url': self.page_url,
            'show_usage': self.show_usage,
            'toggles': toggles,
            'tags': ALL_TAGS,
            'user_counts': user_counts,
            'last_used': last_used,
            'last_modified': last_modified,
        }


class ToggleEditView(ToggleBaseView):
    urlname = 'edit_toggle'
    template_name = 'toggle/edit_flag.html'

    @method_decorator(require_superuser_or_developer)
    def dispatch(self, request, *args, **kwargs):
        return super(ToggleEditView, self).dispatch(request, *args, **kwargs)

    @property
    def page_title(self):
        return "Edit Flag '{}'".format(self.toggle_meta().label)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.toggle_slug])

    @property
    def expanded(self):
        return self.request.GET.get('expand') == 'true'

    @property
    def usage_info(self):
        return self.request.GET.get('usage_info') == 'true'

    @property
    def toggle_slug(self):
        return self.args[0] if len(self.args) > 0 else self.kwargs.get('toggle', "")

    @property
    def static_toggle(self):
        """
        Returns the corresponding toggle definition from corehq/toggles.py
        """
        for toggle in all_toggles():
            if toggle.slug == self.toggle_slug:
                return toggle

    def get_toggle(self):
        if not self.static_toggle:
            raise Http404()
        try:
            return Toggle.get(self.toggle_slug)
        except ResourceNotFound:
            return Toggle(slug=self.toggle_slug)

    def toggle_meta(self):
        toggle_map = self.toggle_map()
        if self.toggle_slug in toggle_map:
            return toggle_map[self.toggle_slug]
        raise Http404

    @property
    def page_context(self):
        toggle_meta = self.toggle_meta()
        toggle = self.get_toggle()
        context = {
            'toggle_meta': toggle_meta,
            'toggle': toggle,
            'expanded': self.expanded,
            'namespaces': [NAMESPACE_USER if n is None else n for n in toggle_meta.namespaces],
            'usage_info': self.usage_info,
        }
        if self.expanded:
            context['domain_toggle_list'] = sorted(
                [(row['key'], toggle_meta.enabled(row['key'])) for row in Domain.get_all(include_docs=False)],
                key=lambda domain_tup: (not domain_tup[1], domain_tup[0])
            )
        if self.usage_info:
            context['last_used'] = _get_usage_info(toggle)
        return context

    def call_save_fn(self, changed_entries, currently_enabled):
        for entry in changed_entries:
            if entry.startswith(NAMESPACE_DOMAIN):
                domain = entry.split(":")[-1]
                if self.static_toggle.save_fn is not None:
                    self.static_toggle.save_fn(domain, entry in currently_enabled)
                toggle_js_domain_cachebuster.clear(domain)
            else:
                # these are sent down with no namespace
                assert ':' not in entry, entry
                username = entry
                toggle_js_user_cachebuster.clear(username)

    def post(self, request, *args, **kwargs):
        toggle = self.get_toggle()
        item_list = request.POST.get('item_list', [])
        if item_list:
            item_list = json.loads(item_list)
            item_list = [u.strip() for u in item_list if u and u.strip()]

        previously_enabled = set(toggle.enabled_users)
        currently_enabled = set(item_list)
        toggle.enabled_users = item_list
        toggle.save()

        changed_entries = previously_enabled ^ currently_enabled  # ^ means XOR
        self.call_save_fn(changed_entries, currently_enabled)
        for item in changed_entries:
            clear_toggle_cache(toggle.slug, item)

        data = {
            'items': item_list
        }
        if self.usage_info:
            data['last_used'] = _get_usage_info(toggle)
        return HttpResponse(json.dumps(data), content_type="application/json")


def _get_usage_info(toggle):
    """Returns usage information for each toggle
    """
    last_used = {}
    active_domains = 0
    for enabled in toggle.enabled_users:
        name = _enabled_item_name(enabled)
        if _namespace_domain(enabled):
            last_form_submission = get_last_form_submission_received(name)
            last_used[name] = _format_date(last_form_submission)
            if last_form_submission:
                active_domains += 1
        else:
            try:
                user = CouchUser.get_by_username(name)
                last_used[name] = _format_date(user.last_login) if user else NOT_FOUND
            except ResourceNotFound:
                last_used[name] = NOT_FOUND
    last_used["_latest"] = _get_most_recently_used(last_used)
    last_used["_active_domains"] = active_domains
    return last_used


def _namespace_domain(enabled_item):
    """Returns whether the enabled item has the domain namespace
    Toggles that are of domain namespace are of the form DOMAIN:{item}
    """
    return enabled_item.split(":")[0] == NAMESPACE_DOMAIN


def _enabled_item_name(enabled_item):
    """Returns the toggle item name
    Toggles are of the form: {namespace}:{toggle_item} or {toggle_item}
    The latter case is used occasionally if the namespace is "USER"
    """
    try:
        return enabled_item.split(":")[1]
    except IndexError:
        return enabled_item.split(":")[0]


def _format_date(date):
    DATE_FORMAT = "%Y-%m-%d"
    if date is None:
        return NOT_FOUND
    return date.strftime(DATE_FORMAT)


def _get_most_recently_used(last_used):
    """Returns the name and date of the most recently used toggle"""
    last_used = {k: v for k, v in last_used.iteritems() if v != NOT_FOUND}
    most_recently_used = sorted(last_used, key=last_used.get, reverse=True)
    return {
        'name': most_recently_used[0],
        'date': last_used[most_recently_used[0]]
    } if most_recently_used else None
