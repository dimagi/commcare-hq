import decimal
import json
from collections import Counter, defaultdict

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.http.response import Http404
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.views.decorators.http import require_POST

from couchdbkit.exceptions import ResourceNotFound

from couchforms.analytics import get_last_form_submission_received
from soil import DownloadBase

from corehq.apps.domain.decorators import require_superuser_or_contractor
from corehq.apps.hqwebapp.decorators import use_datatables
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.toggle_ui.models import ToggleAudit
from corehq.apps.toggle_ui.tasks import generate_toggle_csv_download
from corehq.apps.toggle_ui.utils import (
    find_static_toggle,
    get_subscription_info,
)
from corehq.apps.users.models import CouchUser
from corehq.toggles import (
    ALL_NAMESPACES,
    ALL_TAG_GROUPS,
    NAMESPACE_DOMAIN,
    NAMESPACE_EMAIL_DOMAIN,
    NAMESPACE_USER,
    TAG_CUSTOM,
    TAG_DEPRECATED,
    TAG_INTERNAL,
    DynamicallyPredictablyRandomToggle,
    FeatureRelease,
    PredictablyRandomToggle,
    all_toggles,
    toggles_enabled_for_domain,
    toggles_enabled_for_email_domain,
    toggles_enabled_for_user,
)
from corehq.toggles.models import Toggle
from corehq.toggles.shortcuts import namespaced_item, parse_toggle
from corehq.util import reverse
from corehq.util.soft_assert import soft_assert

NOT_FOUND = "Not Found"


class ToggleListView(BasePageView):
    urlname = 'toggle_list'
    page_title = "Feature Flags"
    template_name = 'toggle/flags.html'

    @use_datatables
    @method_decorator(require_superuser_or_contractor)
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
            'tags': ALL_TAG_GROUPS,
            'user_counts': user_counts,
            'last_used': last_used,
            'last_modified': last_modified,
        }


@method_decorator(require_superuser_or_contractor, name='dispatch')
class ToggleEditView(BasePageView):
    urlname = 'edit_toggle'
    template_name = 'toggle/edit_flag.html'

    @property
    def page_title(self):
        if not self.static_toggle:
            raise Http404()
        return self.static_toggle.label

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
    def is_feature_release(self):
        return isinstance(self.static_toggle, FeatureRelease)

    @cached_property
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

    @property
    def page_context(self):
        toggle = self.get_toggle()
        namespaces = [NAMESPACE_USER if n is None else n for n in self.static_toggle.namespaces]
        context = {
            'static_toggle': self.static_toggle,
            'toggle': toggle,
            'namespaces': namespaces,
            'usage_info': self.usage_info,
            'server_environment': settings.SERVER_ENVIRONMENT,
            'is_random': self.is_random_editable,
            'is_random_editable': self.is_random_editable,
            'is_feature_release': self.is_feature_release,
            'allows_items': all(n in ALL_NAMESPACES for n in namespaces)
        }
        if self.usage_info:
            context['last_used'] = _get_usage_info(toggle)
            context['service_type'], context['by_service'] = _get_service_type(toggle)

        return context

    def post(self, request, *args, **kwargs):
        toggle = self.get_toggle()

        item_list = request.POST.get('item_list', [])
        if item_list:
            item_list = json.loads(item_list)
            item_list = [u.strip() for u in item_list if u and u.strip()]

        previously_enabled = set(toggle.enabled_users)
        currently_enabled = set(item_list)
        toggle.enabled_users = item_list

        randomness = None
        if self.is_random_editable:
            randomness = request.POST.get('randomness', None)
            randomness = decimal.Decimal(randomness) if randomness else None
            self._save_randomness(toggle, randomness)

        toggle.save()

        ToggleAudit.objects.log_toggle_changes(
            self.toggle_slug, self.request.user.username, currently_enabled, previously_enabled, randomness
        )
        _notify_on_change(self.static_toggle, currently_enabled - previously_enabled, self.request.user.username)
        _call_save_fn_and_clear_cache_and_enable_dependencies(
            self.request.user.username, self.static_toggle, previously_enabled, currently_enabled)

        data = {
            'items': item_list
        }
        if self.usage_info:
            data['last_used'] = _get_usage_info(toggle)
            data['service_type'], data['by_service'] = _get_service_type(toggle)
        return JsonResponse(data)

    def _save_randomness(self, toggle, randomness):
        if 0 <= randomness <= 1:
            setattr(toggle, DynamicallyPredictablyRandomToggle.RANDOMNESS_KEY, randomness)
            # clear cache
            if isinstance(self.static_toggle, DynamicallyPredictablyRandomToggle):
                _clear_caches_for_dynamic_toggle(self.static_toggle)
        else:
            messages.error(self.request, "The randomness value {} must be between 0 and 1".format(randomness))


def _notify_on_change(static_toggle, added_entries, username):
    is_deprecated_toggle = (static_toggle.tag in (TAG_DEPRECATED, TAG_CUSTOM, TAG_INTERNAL))
    if added_entries and (static_toggle.notification_emails or is_deprecated_toggle):
        subject = "User {} added {} on {} in environment {}".format(
            username, static_toggle.slug,
            added_entries, settings.SERVER_ENVIRONMENT
        )

        if static_toggle.notification_emails:
            emails = [
                "{}@{}.com".format(email, "dimagi")
                for email in static_toggle.notification_emails
            ]
            _assert = soft_assert(to=emails, send_to_ops=is_deprecated_toggle)
        else:
            _assert = soft_assert(send_to_ops=is_deprecated_toggle)

        _assert(False, subject)


def _call_save_fn_and_clear_cache_and_enable_dependencies(request_username, static_toggle,
                                                          previously_enabled, currently_enabled):
    changed_entries = previously_enabled ^ currently_enabled  # ^ means XOR
    for entry in changed_entries:
        enabled = entry in currently_enabled
        namespace, entry = parse_toggle(entry)
        _call_save_fn_for_toggle(static_toggle, namespace, entry, enabled)
        clear_toggle_cache_by_namespace(namespace, entry)
        _enable_dependencies(request_username, static_toggle, entry, namespace, enabled)


def _enable_dependencies(request_username, static_toggle, item, namespace, is_enabled):
    if is_enabled and static_toggle.parent_toggles:
        for dependency in static_toggle.parent_toggles:
            _set_toggle(request_username, dependency, item, namespace, is_enabled)


def _set_toggle(request_username, static_toggle, item, namespace, is_enabled):
    if static_toggle.set(item=item, enabled=is_enabled, namespace=namespace):
        action = ToggleAudit.ACTION_ADD if is_enabled else ToggleAudit.ACTION_REMOVE
        ToggleAudit.objects.log_toggle_action(
            static_toggle.slug, request_username, [namespaced_item(item, namespace)], action
        )

        if is_enabled:
            _notify_on_change(static_toggle, [item], request_username)

        _enable_dependencies(request_username, static_toggle, item, namespace, is_enabled)


def _call_save_fn_for_toggle(static_toggle, namespace, entry, enabled):
    if namespace == NAMESPACE_DOMAIN:
        domain = entry
        if static_toggle.save_fn is not None:
            static_toggle.save_fn(domain, enabled)


def clear_toggle_cache_by_namespace(namespace, entry):
    if namespace == NAMESPACE_DOMAIN:
        domain = entry
        toggles_enabled_for_domain.clear(domain)
    elif namespace == NAMESPACE_EMAIL_DOMAIN:
        toggles_enabled_for_email_domain.clear(entry)
    else:
        # these are sent down with no namespace
        assert ':' not in entry, entry
        username = entry
        toggles_enabled_for_user.clear(username)


def _clear_caches_for_dynamic_toggle(static_toggle):
    # note: this is rather coupled with python property internals
    DynamicallyPredictablyRandomToggle.randomness.fget.clear(static_toggle)


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


def _get_service_type(toggle):
    """Returns subscription service type for each toggle
    """
    service_type = {}
    for enabled in toggle.enabled_users:
        name = _enabled_item_name(enabled)
        if _namespace_domain(enabled):
            plan_type, plan = get_subscription_info(name)
            service_type[name] = f"{plan_type} : {plan}"

    by_service = defaultdict(list)
    for domain, _type in sorted(service_type.items()):
        by_service[_type].append(domain)

    return service_type, dict(by_service)


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
    last_used = {k: v for k, v in last_used.items() if v != NOT_FOUND}
    most_recently_used = sorted(last_used, key=last_used.get, reverse=True)
    return {
        'name': most_recently_used[0],
        'date': last_used[most_recently_used[0]]
    } if most_recently_used else None


@require_superuser_or_contractor
@require_POST
def set_toggle(request, toggle_slug):
    static_toggle = find_static_toggle(toggle_slug)
    if not static_toggle:
        raise Http404()

    item = request.POST['item']
    enabled = request.POST['enabled'] == 'true'
    namespace = request.POST['namespace']
    _set_toggle(request.user.username, static_toggle, item, namespace, enabled)

    return JsonResponse({'success': True})


@require_superuser_or_contractor
@require_POST
def export_toggles(request):
    tag = request.POST['tag'] or None

    download = DownloadBase()
    download.set_task(generate_toggle_csv_download.delay(
        tag, download.download_id, request.couch_user.username
    ))

    return JsonResponse({
        "download_url": reverse("ajax_job_poll", kwargs={"download_id": download.download_id}),
        "download_id": download.download_id,
    })
