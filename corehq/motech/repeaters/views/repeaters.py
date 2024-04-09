import re
from collections import namedtuple

from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.urls import NoReverseMatch, reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from memoized import memoized

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.views.settings import BaseAdminProjectSettingsView
from corehq.apps.users.decorators import (
    require_can_edit_web_users,
    require_permission,
)
from corehq.apps.users.models import HqPermissions
from corehq.motech.const import PASSWORD_PLACEHOLDER
from corehq.motech.models import ConnectionSettings

from ..const import State
from ..forms import CaseRepeaterForm, FormRepeaterForm, GenericRepeaterForm
from ..models import (
    Repeater,
    SQLRepeatRecord,
    get_all_repeater_types,
)

RepeaterTypeInfo = namedtuple('RepeaterTypeInfo',
                              'class_name friendly_name has_config instances state_counts')


class DomainForwardingOptionsView(BaseAdminProjectSettingsView):
    urlname = 'domain_forwarding'
    page_title = gettext_lazy("Data Forwarding")
    template_name = 'repeaters/repeaters.html'

    @method_decorator(require_permission(HqPermissions.edit_motech))
    @method_decorator(requires_privilege_with_fallback(privileges.DATA_FORWARDING))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @property
    def repeater_types_info(self):
        return [
            RepeaterTypeInfo(
                class_name=r._repeater_type,
                friendly_name=r.friendly_name,
                has_config=r._has_config,
                instances=r.objects.by_domain(self.domain),
            )
            for r in get_all_repeater_types().values()
            if r.available_for_domain(self.domain)
        ]

    @property
    def page_context(self):
        state_counts = SQLRepeatRecord.objects.count_by_repeater_and_state(domain=self.domain)
        return {
            'report': 'repeat_record_report',
            'repeater_types_info': self.repeater_types_info,
            'pending_record_count': sum(
                count for repeater_id, states in state_counts.items()
                for state, count in states.items()
                if state == State.Pending or state == State.Fail
            ),
            'user_can_configure': (
                self.request.couch_user.is_superuser
                or self.request.couch_user.can_edit_motech()
                or toggles.IS_CONTRACTOR.enabled(self.request.couch_user.username)
            ),
            'state_counts': state_counts,
            'State': State,
        }


class BaseRepeaterView(BaseAdminProjectSettingsView):
    page_title = gettext_lazy("Forward Data")
    repeater_form_class = GenericRepeaterForm
    template_name = 'repeaters/add_form_repeater.html'

    @method_decorator(require_permission(HqPermissions.edit_motech))
    @method_decorator(requires_privilege_with_fallback(privileges.DATA_FORWARDING))
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
        assert repeater.repeater_id, repeater
        repeater.domain = self.domain
        repeater.connection_settings_id = int(cleaned_data['connection_settings_id'])
        repeater.request_method = cleaned_data['request_method']
        repeater.format = cleaned_data['format']
        name = cleaned_data.get('name')
        if not name:
            conn_settings = ConnectionSettings.objects.get(pk=repeater.connection_settings_id)
            name = conn_settings.name
        repeater.name = name
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
        messages.success(request, _("Forwarding set up to {}").format(repeater.name))
        return HttpResponseRedirect(
            reverse(DomainForwardingOptionsView.urlname, args=[self.domain])
        )


class EditRepeaterView(BaseRepeaterView):
    urlname = 'edit_repeater'
    template_name = 'repeaters/add_form_repeater.html'

    @property
    def repeater_id(self):
        return self.kwargs['repeater_id']

    @property
    def page_url(self):
        # The EditRepeaterView url routes to the correct edit form for
        # its subclasses. It does this with `repeater_type` in
        # r'^forwarding/(?P<repeater_type>\w+)/edit/(?P<repeater_id>\w+)/$'
        # See corehq/apps/domain/urls.py for details.
        return reverse(EditRepeaterView.urlname,
                       args=[self.domain, self.repeater_type, self.repeater_id])

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
            repeater = Repeater.objects.get(id=repeater_id)
            data = repeater.to_json()
            data['password'] = PASSWORD_PLACEHOLDER
            return self.repeater_form_class(
                domain=self.domain,
                repeater_class=self.repeater_class,
                data=data,
                submit_btn_text=_("Update Forwarder"),
            )

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        if self.request.GET.get('repeater_type'):
            self.kwargs['repeater_type'] = self.request.GET['repeater_type']
        return super(EditRepeaterView, self).dispatch(request, *args, **kwargs)

    def initialize_repeater(self):
        return Repeater.objects.get(id=self.kwargs['repeater_id'])

    def post_save(self, request, repeater):
        messages.success(request, _("Forwarder Successfully Updated"))
        try:
            url = reverse(self.urlname, args=[self.domain, repeater.repeater_id])
        except NoReverseMatch:
            url = reverse(self.urlname, args=[self.domain, repeater.repeater_type, repeater.repeater_id])
        return HttpResponseRedirect(url)


class AddFormRepeaterView(AddRepeaterView):
    urlname = 'add_form_repeater'
    repeater_form_class = FormRepeaterForm

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def set_repeater_attr(self, repeater, cleaned_data):
        repeater = super().set_repeater_attr(repeater, cleaned_data)
        repeater.include_app_id_param = (
            self.add_repeater_form.cleaned_data['include_app_id_param'])
        repeater.user_blocklist = (
            self.add_repeater_form.cleaned_data['user_blocklist'])
        repeater.white_listed_form_xmlns = [xmlns for xmlns in re.split(
            r'[, \r\n]',
            self.add_repeater_form.cleaned_data['white_listed_form_xmlns'],
        ) if xmlns]
        return repeater


class EditFormRepeaterView(EditRepeaterView, AddFormRepeaterView):
    urlname = 'edit_form_repeater'
    page_title = gettext_lazy("Edit Form Repeater")

    @property
    def page_url(self):
        return reverse(AddFormRepeaterView.urlname, args=[self.domain])


class AddCaseRepeaterView(AddRepeaterView):
    urlname = 'add_case_repeater'
    repeater_form_class = CaseRepeaterForm

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def set_repeater_attr(self, repeater, cleaned_data):
        repeater = super().set_repeater_attr(repeater, cleaned_data)
        repeater.white_listed_case_types = (
            self.add_repeater_form.cleaned_data['white_listed_case_types'])
        repeater.black_listed_users = (
            self.add_repeater_form.cleaned_data['black_listed_users'])
        return repeater


class EditCaseRepeaterView(EditRepeaterView, AddCaseRepeaterView):
    urlname = 'edit_case_repeater'
    page_title = gettext_lazy("Edit Case Repeater")

    @property
    def page_url(self):
        return reverse(AddCaseRepeaterView.urlname, args=[self.domain])


class EditReferCaseRepeaterView(EditCaseRepeaterView):
    urlname = "edit_refer_case_repeater"


class EditDataRegistryCaseUpdateRepeater(EditCaseRepeaterView):
    urlname = "edit_data_registry_case_update_repeater"


@require_POST
@require_can_edit_web_users
@requires_privilege_with_fallback(privileges.DATA_FORWARDING)
def drop_repeater(request, domain, repeater_id):
    rep = Repeater.objects.get(id=repeater_id)
    rep.retire()
    messages.success(request, "Forwarding stopped!")
    return HttpResponseRedirect(
        reverse(DomainForwardingOptionsView.urlname, args=[domain])
    )


@require_POST
@require_can_edit_web_users
@requires_privilege_with_fallback(privileges.DATA_FORWARDING)
def pause_repeater(request, domain, repeater_id):
    rep = Repeater.objects.get(id=repeater_id)
    rep.pause()
    messages.success(request, "Forwarding paused!")
    return HttpResponseRedirect(
        reverse(DomainForwardingOptionsView.urlname, args=[domain])
    )


@require_POST
@require_can_edit_web_users
@requires_privilege_with_fallback(privileges.DATA_FORWARDING)
def resume_repeater(request, domain, repeater_id):
    rep = Repeater.objects.get(id=repeater_id)
    rep.resume()
    messages.success(request, "Forwarding resumed!")
    return HttpResponseRedirect(
        reverse(DomainForwardingOptionsView.urlname, args=[domain])
    )
