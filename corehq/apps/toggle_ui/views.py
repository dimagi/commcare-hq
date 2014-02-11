import json
from couchdbkit.exceptions import ResourceNotFound
from django.core.urlresolvers import reverse
from django.http.response import Http404, HttpResponse
from django.utils.decorators import method_decorator
from corehq import toggles
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.views import BasePageView
from toggle.models import Toggle, generate_toggle_id


class ToggleBaseView(BasePageView):

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(ToggleBaseView, self).dispatch(request, *args, **kwargs)

    def all_toggles(self):
        for toggle in dir(toggles):
            if not toggle.startswith('__'):
                yield getattr(toggles, toggle)


class ToggleListView(ToggleBaseView):
    urlname = 'toggle_list'
    page_title = "Feature Flags"
    template_name = 'toggle/flags.html'

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def page_context(self):
        return {
            'toggles': self.all_toggles(),
        }


class ToggleEditView(ToggleBaseView):
    urlname = 'edit_toggle'
    template_name = 'toggle/edit_flag.html'

    @property
    def page_title(self):
        return "Edit Flag '{}'".format(self.toggle_slug)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.toggle_slug])

    @property
    def toggle_slug(self):
        return self.args[0] if len(self.args) > 0 else self.kwargs.get('toggle', "")

    def get_toggle(self):
        if not self.toggle_slug in list(self.all_toggles()):
            raise Http404()
        try:
            return Toggle.get(generate_toggle_id(self.toggle_slug))
        except ResourceNotFound:
            return Toggle(slug=self.toggle_slug)

    @property
    def page_context(self):
        return {
            'toggle': self.get_toggle(),
        }

    def post(self, request, *args, **kwargs):
        toggle = self.get_toggle()
        user_list = request.POST.get('user_list', [])
        if user_list:
            user_list = json.loads(user_list)
            user_list = [u for u in user_list if u]

        toggle.enabled_users = user_list
        toggle.save()
        data = {
            'user_list': user_list
        }
        return HttpResponse(json.dumps(data), mimetype="application/json")