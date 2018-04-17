from __future__ import absolute_import
from __future__ import unicode_literals
import json
from collections import Counter
from couchdbkit.exceptions import ResourceNotFound
import decimal
from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.http.response import Http404, HttpResponse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_js_domain_cachebuster, \
    toggle_js_user_cachebuster
from couchforms.analytics import get_last_form_submission_received
from corehq.apps.domain.decorators import require_superuser_or_developer
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.toggle_ui.utils import find_static_toggle
from corehq.apps.users.models import CouchUser
from corehq.apps.hqwebapp.decorators import use_datatables
from corehq.toggles import all_toggles, ALL_TAGS, NAMESPACE_USER, NAMESPACE_DOMAIN, \
    DynamicallyPredictablyRandomToggle, PredictablyRandomToggle, ALL_NAMESPACES
from toggle.models import Toggle
from toggle.shortcuts import clear_toggle_cache, parse_toggle
import six

NOT_FOUND = "Not Found"


class ToggleBaseView(BasePageView):

    @method_decorator(require_superuser_or_developer)
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
        return self.toggle_meta().label

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.toggle_slug])

    @property
    def usage_info(self):
        return self.request.GET.get('usage_info') == 'true'

    @property
    def toggle_slug(self):
        return self.args[0] if len(self.args) > 0 else self.kwargs.get('toggle', "")

    @property
    def is_random(self):
        return isinstance(self.static_toggle, PredictablyRandomToggle)

    @property
    def is_random_editable(self):
        return isinstance(self.static_toggle, DynamicallyPredictablyRandomToggle)

    @property
    def static_toggle(self):
        """
        Returns the corresponding toggle definition from corehq/toggles.py
        """
        return find_static_toggle(self.toggle_slug)

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
        namespaces = [NAMESPACE_USER if n is None else n for n in toggle_meta.namespaces]
        context = {
            'toggle_meta': toggle_meta,
            'toggle': toggle,
            'namespaces': namespaces,
            'usage_info': self.usage_info,
            'server_environment': settings.SERVER_ENVIRONMENT,
            'is_random': self.is_random_editable,
            'is_random_editable': self.is_random_editable,
            'allows_items': all(n in ALL_NAMESPACES for n in namespaces)
        }
        if self.usage_info:
            context['last_used'] = _get_usage_info(toggle)
        return context

    def post(self, request, *args, **kwargs):
        toggle = self.get_toggle()
        item_list = request.POST.get('item_list', [])
        randomness = request.POST.get('randomness', None)
        randomness = decimal.Decimal(randomness) if randomness else None
        if item_list:
            item_list = json.loads(item_list)
            item_list = [u.strip() for u in item_list if u and u.strip()]

        previously_enabled = set(toggle.enabled_users)
        currently_enabled = set(item_list)
        toggle.enabled_users = item_list

        save_randomness = (
            self.is_random_editable and randomness is not None
        )
        if save_randomness and (0 <= randomness <= 1):
            setattr(toggle, DynamicallyPredictablyRandomToggle.RANDOMNESS_KEY, randomness)
            # clear cache
            if isinstance(self.toggle_meta(), DynamicallyPredictablyRandomToggle):
                _clear_caches_for_dynamic_toggle(self.toggle_meta())

        elif save_randomness:
            messages.error(request, _("The randomness value {} must be between 0 and 1".format(randomness)))

        toggle.save()

        changed_entries = previously_enabled ^ currently_enabled  # ^ means XOR
        _call_save_fn_and_clear_cache(toggle.slug, changed_entries, currently_enabled, self.static_toggle)

        data = {
            'items': item_list
        }
        if self.usage_info:
            data['last_used'] = _get_usage_info(toggle)
        return HttpResponse(json.dumps(data), content_type="application/json")


def toggle_app_manager_v2(request):
    slug = "app_manager_v2"
    on_or_off = request.POST.get('on_or_off', 'on')
    try:
        toggle = Toggle.get(slug)
    except ResourceNotFound:
        toggle = Toggle(slug=slug)

    enable = on_or_off == "on"
    enabled = request.user.username in toggle.enabled_users
    if enable != enabled:
        changed_entries = [request.user.username]
        if enable:
            toggle.enabled_users.append(request.user.username)
        else:
            toggle.enabled_users.remove(request.user.username)
        toggle.save()
        _call_save_fn_and_clear_cache(slug, changed_entries, toggle.enabled_users, find_static_toggle(slug))

    return HttpResponse(json.dumps({'success': True}), content_type="application/json")


def _call_save_fn_and_clear_cache(toggle_slug, changed_entries, currently_enabled, static_toggle):
    for entry in changed_entries:
        enabled = entry in currently_enabled
        namespace, entry = parse_toggle(entry)
        if namespace == NAMESPACE_DOMAIN:
            domain = entry
            if static_toggle.save_fn is not None:
                static_toggle.save_fn(domain, enabled)
            toggle_js_domain_cachebuster.clear(domain)
        else:
            # these are sent down with no namespace
            assert ':' not in entry, entry
            username = entry
            toggle_js_user_cachebuster.clear(username)

        clear_toggle_cache(toggle_slug, entry, namespace=namespace)


def _clear_caches_for_dynamic_toggle(toggle_meta):
    # note: this is rather coupled with python property internals
    DynamicallyPredictablyRandomToggle.randomness.fget.clear(toggle_meta)
    # also have to do this since the toggle itself is cached
    all_toggles.clear()


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
    last_used = {k: v for k, v in six.iteritems(last_used) if v != NOT_FOUND}
    most_recently_used = sorted(last_used, key=last_used.get, reverse=True)
    return {
        'name': most_recently_used[0],
        'date': last_used[most_recently_used[0]]
    } if most_recently_used else None
