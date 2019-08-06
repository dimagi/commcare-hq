from __future__ import absolute_import

from __future__ import unicode_literals
import json
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_lazy
from django.views.decorators.http import require_POST

from memoized import memoized

from corehq.motech.const import PASSWORD_PLACEHOLDER, ALGO_AES
from corehq.motech.utils import b64_aes_encrypt
from dimagi.utils.post import simple_post

from corehq import toggles
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.views.settings import BaseAdminProjectSettingsView, BaseProjectSettingsView
from corehq.apps.users.decorators import require_can_edit_web_users, require_permission
from corehq.apps.users.models import Permissions

from corehq.motech.repeaters.forms import (
    CaseRepeaterForm,
    FormRepeaterForm,
    GenericRepeaterForm,
    OpenmrsRepeaterForm,
    Dhis2RepeaterForm,
)
from corehq.motech.repeaters.models import Repeater, RepeatRecord, BASIC_AUTH, DIGEST_AUTH
from corehq.motech.repeaters.repeater_generators import RegisterGenerator
from corehq.motech.repeaters.utils import get_all_repeater_types


class DomainForwardingOptionsView(BaseAdminProjectSettingsView):
    urlname = 'domain_forwarding'
    page_title = ugettext_lazy("Data Forwarding")
    template_name = 'repeaters/repeaters.html'

    @method_decorator(require_permission(Permissions.edit_motech))
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def repeaters(self):
        return [
            (
                r.__name__,
                r.by_domain(self.domain),
                r.friendly_name,
                r.get_custom_url(self.domain)
            )
            for r in get_all_repeater_types().values() if r.available_for_domain(self.domain)
        ]

    @property
    def page_context(self):
        return {
            'repeaters': self.repeaters,
            'pending_record_count': RepeatRecord.count(self.domain),
            'gefingerpoken': (
                # Set gefingerpoken_ to whether the user should be allowed to change MOTECH configuration.
                # .. _gefingerpoken: https://en.wikipedia.org/wiki/Blinkenlights
                self.request.couch_user.is_superuser or
                self.request.couch_user.can_edit_motech() or
                toggles.IS_CONTRACTOR.enabled(self.request.couch_user.username)
            )
        }


class BaseRepeaterView(BaseAdminProjectSettingsView):
    page_title = ugettext_lazy("Forward Data")
    repeater_form_class = GenericRepeaterForm
    template_name = 'repeaters/add_form_repeater.html'

    @method_decorator(require_permission(Permissions.edit_motech))
    def dispatch(self, request, *args, **kwargs):
        return super(BaseRepeaterView, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.repeater_type])

    @property
    def parent_pages(self):
        return [{
            'title': DomainForwardingOptionsView.page_title,
            'url': reverse(DomainForwardingOptionsView.urlname, args=[self.domain]),
        }]

    @property
    def repeater_type(self):
        return self.kwargs['repeater_type']

    @property
    def page_name(self):
        return self.repeater_class.friendly_name

    @property
    @memoized
    def repeater_class(self):
        try:
            return get_all_repeater_types()[self.repeater_type]
        except KeyError:
            raise Http404(
                "No such repeater {}. Valid types: {}".format(
                    self.repeater_type, list(get_all_repeater_types())
                )
            )

    @property
    def add_repeater_form(self):
        return None

    @property
    def page_context(self):
        return {
            'form': self.add_repeater_form,
            'repeater_type': self.repeater_type,
        }

    def initialize_repeater(self):
        raise NotImplementedError

    def make_repeater(self):
        repeater = self.initialize_repeater()
        return self.set_repeater_attr(repeater, self.add_repeater_form.cleaned_data)

    def set_repeater_attr(self, repeater, cleaned_data):
        repeater.domain = self.domain
        repeater.url = cleaned_data['url']
        repeater.auth_type = cleaned_data['auth_type'] or None
        repeater.username = cleaned_data['username']
        if cleaned_data['password'] != PASSWORD_PLACEHOLDER:
            repeater.password = '${algo}${ciphertext}'.format(
                algo=ALGO_AES,
                ciphertext=b64_aes_encrypt(cleaned_data['password'])
            )
        repeater.format = cleaned_data['format']
        repeater.skip_cert_verify = cleaned_data['skip_cert_verify']
        return repeater

    def post_save(self, request, repeater):
        pass

    def post(self, request, *args, **kwargs):
        if self.add_repeater_form.is_valid():
            repeater = self.make_repeater()
            repeater.save()
            return self.post_save(request, repeater)
        return self.get(request, *args, **kwargs)


class AddRepeaterView(BaseRepeaterView):
    urlname = 'add_repeater'

    @property
    @memoized
    def add_repeater_form(self):
        if self.request.method == 'POST':
            return self.repeater_form_class(
                self.request.POST,
                domain=self.domain,
                repeater_class=self.repeater_class
            )
        return self.repeater_form_class(
            domain=self.domain,
            repeater_class=self.repeater_class
        )

    def initialize_repeater(self):
        return self.repeater_class()

    def post_save(self, request, repeater):
        messages.success(request, _("Forwarding set up to %s" % repeater.url))
        return HttpResponseRedirect(reverse(DomainForwardingOptionsView.urlname, args=[self.domain]))


class AddFormRepeaterView(AddRepeaterView):
    urlname = 'add_form_repeater'
    repeater_form_class = FormRepeaterForm

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def set_repeater_attr(self, repeater, cleaned_data):
        repeater = super(AddFormRepeaterView, self).set_repeater_attr(repeater, cleaned_data)
        repeater.include_app_id_param = self.add_repeater_form.cleaned_data['include_app_id_param']
        return repeater


class AddCaseRepeaterView(AddRepeaterView):
    urlname = 'add_case_repeater'
    repeater_form_class = CaseRepeaterForm

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def set_repeater_attr(self, repeater, cleaned_data):
        repeater = super(AddCaseRepeaterView, self).set_repeater_attr(repeater, cleaned_data)
        repeater.white_listed_case_types = self.add_repeater_form.cleaned_data['white_listed_case_types']
        repeater.black_listed_users = self.add_repeater_form.cleaned_data['black_listed_users']
        return repeater


class AddOpenmrsRepeaterView(AddCaseRepeaterView):
    urlname = 'new_openmrs_repeater$'
    repeater_form_class = OpenmrsRepeaterForm
    page_title = ugettext_lazy("Forward to OpenMRS")
    page_name = ugettext_lazy("Forward to OpenMRS")

    def set_repeater_attr(self, repeater, cleaned_data):
        repeater = super(AddOpenmrsRepeaterView, self).set_repeater_attr(repeater, cleaned_data)
        repeater.location_id = self.add_repeater_form.cleaned_data['location_id']
        repeater.atom_feed_enabled = self.add_repeater_form.cleaned_data['atom_feed_enabled']
        return repeater


class AddDhis2RepeaterView(AddFormRepeaterView):
    urlname = 'new_dhis2_repeater$'
    repeater_form_class = Dhis2RepeaterForm
    page_title = ugettext_lazy("Forward Forms to DHIS2 as Anonymous Events")
    page_name = ugettext_lazy("Forward Forms to DHIS2 as Anonymous Events")

    def set_repeater_attr(self, repeater, cleaned_data):
        repeater = super(AddDhis2RepeaterView, self).set_repeater_attr(repeater, cleaned_data)
        repeater.include_app_id_param = self.add_repeater_form.cleaned_data['include_app_id_param']
        return repeater


class EditRepeaterView(BaseRepeaterView):
    urlname = 'edit_repeater'
    template_name = 'repeaters/add_form_repeater.html'

    @property
    def repeater_id(self):
        return self.kwargs['repeater_id']

    @property
    def page_url(self):
        # The EditRepeaterView url routes to the correct edit form for its subclasses. It does this with
        # `repeater_type` in r'^forwarding/(?P<repeater_type>\w+)/edit/(?P<repeater_id>\w+)/$'
        # See corehq/apps/domain/urls.py for details.
        return reverse(EditRepeaterView.urlname, args=[self.domain, self.repeater_type, self.repeater_id])

    @property
    @memoized
    def add_repeater_form(self):
        if self.request.method == 'POST':
            return self.repeater_form_class(
                self.request.POST,
                domain=self.domain,
                repeater_class=self.repeater_class
            )
        else:
            repeater_id = self.kwargs['repeater_id']
            repeater = Repeater.get(repeater_id)
            data = repeater.to_json()
            data['password'] = PASSWORD_PLACEHOLDER
            return self.repeater_form_class(
                domain=self.domain,
                repeater_class=self.repeater_class,
                data=data,
                submit_btn_text=_("Update Repeater"),
            )

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        if self.request.GET.get('repeater_type'):
            self.kwargs['repeater_type'] = self.request.GET['repeater_type']
        return super(EditRepeaterView, self).dispatch(request, *args, **kwargs)

    def initialize_repeater(self):
        return Repeater.get(self.kwargs['repeater_id'])

    def post_save(self, request, repeater):
        messages.success(request, _("Repeater Successfully Updated"))
        if self.request.GET.get('repeater_type'):
            return HttpResponseRedirect(
                (reverse(self.urlname, args=[self.domain, repeater.get_id]) +
                 '?repeater_type=' + self.kwargs['repeater_type'])
            )
        else:
            return HttpResponseRedirect(reverse(self.urlname, args=[self.domain, repeater.get_id]))


class EditCaseRepeaterView(EditRepeaterView, AddCaseRepeaterView):
    urlname = 'edit_case_repeater'
    page_title = ugettext_lazy("Edit Case Repeater")

    @property
    def page_url(self):
        return reverse(AddCaseRepeaterView.urlname, args=[self.domain])


class EditFormRepeaterView(EditRepeaterView, AddFormRepeaterView):
    urlname = 'edit_form_repeater'
    page_title = ugettext_lazy("Edit Form Repeater")

    @property
    def page_url(self):
        return reverse(AddFormRepeaterView.urlname, args=[self.domain])


class EditOpenmrsRepeaterView(EditRepeaterView, AddOpenmrsRepeaterView):
    urlname = 'edit_openmrs_repeater'
    page_title = ugettext_lazy("Edit OpenMRS Repeater")


class EditDhis2RepeaterView(EditRepeaterView, AddDhis2RepeaterView):
    urlname = 'edit_dhis2_repeater'
    page_title = ugettext_lazy("Edit DHIS2 Anonymous Event Repeater")


@require_POST
@require_can_edit_web_users
def drop_repeater(request, domain, repeater_id):
    rep = Repeater.get(repeater_id)
    rep.retire()
    messages.success(request, "Forwarding stopped!")
    return HttpResponseRedirect(reverse(DomainForwardingOptionsView.urlname, args=[domain]))


@require_POST
@require_can_edit_web_users
def pause_repeater(request, domain, repeater_id):
    rep = Repeater.get(repeater_id)
    rep.pause()
    messages.success(request, "Forwarding paused!")
    return HttpResponseRedirect(reverse(DomainForwardingOptionsView.urlname, args=[domain]))


@require_POST
@require_can_edit_web_users
def resume_repeater(request, domain, repeater_id):
    rep = Repeater.get(repeater_id)
    rep.resume()
    messages.success(request, "Forwarding resumed!")
    return HttpResponseRedirect(reverse(DomainForwardingOptionsView.urlname, args=[domain]))


@require_POST
@require_can_edit_web_users
def test_repeater(request, domain):
    url = request.POST["url"]
    repeater_type = request.POST['repeater_type']
    format = request.POST.get('format', None)
    repeater_class = get_all_repeater_types()[repeater_type]
    auth_type = request.POST.get('auth_type')

    form = GenericRepeaterForm(
        {"url": url, "format": format},
        domain=domain,
        repeater_class=repeater_class
    )
    if form.is_valid():
        url = form.cleaned_data["url"]
        format = format or RegisterGenerator.default_format_by_repeater(repeater_class)
        generator_class = RegisterGenerator.generator_class_by_repeater_format(repeater_class, format)
        generator = generator_class(repeater_class())
        fake_post = generator.get_test_payload(domain)
        headers = generator.get_headers()

        username = request.POST.get('username')
        password = request.POST.get('password')
        verify = not request.POST.get('skip_cert_verify') == 'true'
        if auth_type == BASIC_AUTH:
            auth = HTTPBasicAuth(username, password)
        elif auth_type == DIGEST_AUTH:
            auth = HTTPDigestAuth(username, password)
        else:
            auth = None

        try:
            resp = simple_post(fake_post, url, headers=headers, auth=auth, verify=verify)
            if 200 <= resp.status_code < 300:
                return HttpResponse(json.dumps({"success": True,
                                                "response": resp.text,
                                                "status": resp.status_code}))
            else:
                return HttpResponse(json.dumps({"success": False,
                                                "response": resp.text,
                                                "status": resp.status_code}))

        except Exception as e:
            errors = str(e)
        return HttpResponse(json.dumps({"success": False, "response": errors}))
    else:
        return HttpResponse(json.dumps({"success": False, "response": "Please enter a valid url."}))
