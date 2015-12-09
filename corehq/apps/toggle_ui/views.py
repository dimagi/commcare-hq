import json
from collections import Counter
from couchdbkit.exceptions import ResourceNotFound
from django.core.urlresolvers import reverse
from django.http.response import Http404, HttpResponse
from django.utils.decorators import method_decorator
from corehq.apps.domain.models import Domain
from corehq.apps.domain.decorators import require_superuser_or_developer
from corehq.apps.hqwebapp.views import BasePageView
from corehq.toggles import all_toggles, ALL_TAGS, NAMESPACE_USER, NAMESPACE_DOMAIN
from toggle.models import Toggle
from toggle.shortcuts import clear_toggle_cache


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
        user_counts = {}
        if self.show_usage:
            for t in toggles:
                counter = Counter()
                try:
                    usage = Toggle.get(t.slug)
                except ResourceNotFound:
                    domain_counts[t.slug] = 0
                    user_counts[t.slug] = 0
                else:
                    for u in usage.enabled_users:
                        namespace = u.split(":", 1)[0] if u.find(":") != -1 else NAMESPACE_USER
                        counter[namespace] += 1
                    domain_counts[t.slug] = counter.get(NAMESPACE_DOMAIN, 0)
                    user_counts[t.slug] = counter.get(NAMESPACE_USER, 0)

        return {
            'domain_counts': domain_counts,
            'page_url': self.page_url,
            'show_usage': self.show_usage,
            'toggles': toggles,
            'tags': ALL_TAGS,
            'user_counts': user_counts,
        }


class ToggleEditView(ToggleBaseView):
    urlname = 'edit_toggle'
    template_name = 'toggle/edit_flag.html'

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
        context = {
            'toggle_meta': toggle_meta,
            'toggle': self.get_toggle(),
            'expanded': self.expanded,
            'namespaces': [NAMESPACE_USER if n is None else n for n in toggle_meta.namespaces],
        }
        if self.expanded:
            context['domain_toggle_list'] = sorted(
                [(row['key'], toggle_meta.enabled(row['key'])) for row in Domain.get_all(include_docs=False)],
                key=lambda domain_tup: (not domain_tup[1], domain_tup[0])
            )
        return context

    def call_save_fn(self, changed_entries, currently_enabled):
        if self.static_toggle.save_fn is None:
            return
        for entry in changed_entries:
            if entry.startswith(NAMESPACE_DOMAIN):
                domain = entry.split(":")[-1]
                self.static_toggle.save_fn(domain, entry in currently_enabled)

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
            'item_list': item_list
        }
        return HttpResponse(json.dumps(data), content_type="application/json")
