from django.http import HttpResponse
from django.urls import reverse
from django.utils.decorators import method_decorator

from corehq.apps.domain.decorators import login_required
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.styleguide.examples.bootstrap5.htmx_complex_store import KeyValuePairStore
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


@method_decorator(login_required, name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class HtmxKeyValuePairsDemoView(HqHtmxActionMixin, BasePageView):
    """
    A simple HTMX demo that manages key/value pairs on the server side
    using a CacheStore instead of a client-side array.
    """

    urlname = 'sg_htmx_key_value_demo'
    template_name = 'styleguide/htmx_key_values/main.html'
    list_template = 'styleguide/htmx_key_values/partial.html'
    error_value_template = 'styleguide/htmx_key_values/field_with_error.html'

    @property
    def page_url(self):
        return reverse(self.urlname)

    def _store(self):
        return KeyValuePairStore(self.request)

    def get_pairs(self):
        return self._store().get()

    def save_pairs(self, pairs):
        self._store().set(pairs)

    def _next_id(self, pairs):
        if not pairs:
            return 1
        return max(p['id'] for p in pairs) + 1

    def render_pairs(self, request):
        """
        Helper to render the partial containing the list. We always target the
        same container in the template and let HTMX replace it.
        """
        return self.render_htmx_partial_response(
            request,
            self.list_template,
            {
                'pairs': self.get_pairs(),
            },
        )

    @hq_hx_action('get')
    def load_pairs(self, request, *args, **kwargs):
        """
        Load the current list of key/value pairs.
        """
        return self.render_pairs(request)

    @hq_hx_action('post')
    def add_pair(self, request, *args, **kwargs):
        """
        Add a new, empty key/value row at the end of the list.
        """
        pairs = self.get_pairs()
        pairs.append(
            {
                'id': self._next_id(pairs),
                'key': '',
                'value': '',
            }
        )
        self.save_pairs(pairs)
        return self.render_pairs(request)

    @hq_hx_action('post')
    def update_pair(self, request, *args, **kwargs):
        """
        Update a single field ('key' or 'value') for a specific row.
        """
        pair_id = int(request.POST['id'])
        field = request.POST['field']  # "key" or "value"
        new_value = request.POST.get(field, '')

        pairs = self.get_pairs()
        pair = next((p for p in pairs if p['id'] == pair_id), None)

        if pair is None or field not in ('key', 'value'):
            # Example of a generic error (could also raise HtmxResponseException)
            response = HttpResponse('Invalid pair', status=400)
            return response

        pairs = self.get_pairs()
        for pair in pairs:
            if pair['id'] == pair_id and field in ('key', 'value'):
                pair[field] = new_value
                break

        has_error = field == 'value' and not new_value.strip()
        had_error = field == 'value' and 'error' in request.POST
        if has_error or had_error:
            # Render just the field-with-error fragment
            context = {'pair': pair}
            if has_error:
                context['error'] = 'Value cannot be blank.'
            response = self.render_htmx_partial_response(
                request,
                self.error_value_template,
                context,
            )
            # Override hx-swap="none" and target a specific wrapper element
            response['HX-Reswap'] = 'outerHTML'
            response['HX-Retarget'] = f'#pair-{pair_id}-value'
            return response

        self.save_pairs(pairs)
        return self.render_htmx_no_response(request)

    @hq_hx_action('post')
    def delete_pair(self, request, *args, **kwargs):
        """
        Remove a row entirely.
        """
        pair_id = int(request.POST['id'])
        pairs = [p for p in self.get_pairs() if p['id'] != pair_id]
        self.save_pairs(pairs)
        return self.render_pairs(request)
