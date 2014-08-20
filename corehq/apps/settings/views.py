from django.views.decorators.debug import sensitive_post_parameters
from corehq.apps.style.decorators import use_bootstrap_3
from dimagi.utils.couch.resource_conflict import retry_resource
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.views.decorators.http import require_POST
import langcodes

from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from corehq import MySettingsTab
from corehq.apps.domain.decorators import (login_and_domain_required, require_superuser,
                                           login_required)
from django.core.urlresolvers import reverse
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.hqwebapp.views import BaseSectionPageView
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.web import json_response

@login_and_domain_required
def default(request, domain):
    return HttpResponseRedirect(reverse("users_default", args=[domain]))

@login_and_domain_required
def redirect_users(request, domain, old_url=""):
    return HttpResponseRedirect(reverse("users_default", args=[domain]))

@login_and_domain_required
def redirect_domain_settings(request, domain, old_url=""):
    return HttpResponseRedirect(reverse("domain_forwarding", args=[domain]))


@require_superuser
def project_id_mapping(request, domain):
    from corehq.apps.users.models import CommCareUser
    from corehq.apps.groups.models import Group

    users = CommCareUser.by_domain(domain)
    groups = Group.by_domain(domain)

    return json_response({
        'users': dict([(user.raw_username, user.user_id) for user in users]),
        'groups': dict([(group.name, group.get_id) for group in groups]),
    })


class BaseMyAccountView(BaseSectionPageView):
    section_name = ugettext_lazy("My Account")

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add the login_required decorator
        return super(BaseMyAccountView, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def main_context(self):
        context = super(BaseMyAccountView, self).main_context
        context.update({
            'active_tab': MySettingsTab(
                self.request,
                self.urlname,
                couch_user=self.request.couch_user
            ),
            'is_my_account_settings': True,
        })
        return context

    @property
    def section_url(self):
        return reverse(MyAccountSettingsView.urlname)


class DefaultMySettingsView(BaseMyAccountView):
    urlname = "default_my_settings"

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse(MyAccountSettingsView.urlname))


class MyAccountSettingsView(BaseMyAccountView):
    urlname = 'my_account_settings'
    page_title = ugettext_lazy("My Information")
    template_name = 'settings/edit_my_account.html'

    @method_decorator(use_bootstrap_3())
    def dispatch(self, request, *args, **kwargs):
        return super(MyAccountSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def settings_form(self):
        language_choices = langcodes.get_all_langs_for_select()
        from corehq.apps.users.forms import UpdateMyAccountInfoForm
        if self.request.method == 'POST':
            form = UpdateMyAccountInfoForm(self.request.POST)
        else:
            form = UpdateMyAccountInfoForm()
        form.initialize_form(existing_user=self.request.couch_user)
        form.load_language(language_choices)
        return form

    @property
    def page_context(self):
        return {
            'form': self.settings_form,
        }

    def post(self, request, *args, **kwargs):
        if self.settings_form.is_valid():
            old_lang = self.request.couch_user.language
            self.settings_form.update_user(existing_user=self.request.couch_user)
            new_lang = self.request.couch_user.language
            # set language in the session so it takes effect immediately
            if new_lang != old_lang:
                request.session['django_language'] = new_lang
        return self.get(request, *args, **kwargs)


class MyProjectsList(BaseMyAccountView):
    urlname = 'my_projects'
    page_title = ugettext_lazy("My Projects")
    template_name = 'settings/my_projects.html'

    @property
    def all_domains(self):
        all_domains = self.request.couch_user.get_domains()
        for d in all_domains:
            yield {
                'name': d,
                'is_admin': self.request.couch_user.is_domain_admin(d)
            }

    @property
    def page_context(self):
        return {
            'domains': self.all_domains
        }

    @property
    @memoized
    def domain_to_remove(self):
        if self.request.method == 'POST':
            return self.request.POST['domain']

    def post(self, request, *args, **kwargs):
        if self.request.couch_user.is_domain_admin(self.domain_to_remove):
            messages.error(request, _("Unable remove membership because you are the admin of %s")
                                    % self.domain_to_remove)
        else:
            try:
                self.request.couch_user.delete_domain_membership(self.domain_to_remove, create_record=True)
                self.request.couch_user.save()
                messages.success(request, _("You are no longer part of the project %s") % self.domain_to_remove)
            except Exception:
                messages.error(request, _("There was an error removing you from this project."))
        return self.get(request, *args, **kwargs)


class ChangeMyPasswordView(BaseMyAccountView):
    urlname = 'change_my_password'
    template_name = 'settings/change_my_password.html'
    page_title = ugettext_lazy("Change My Password")

    @property
    @memoized
    def password_change_form(self):
        if self.request.method == 'POST':
            return PasswordChangeForm(user=self.request.user, data=self.request.POST)
        return PasswordChangeForm(user=self.request.user)

    @property
    def page_context(self):
        return {
            'form': self.password_change_form,
        }

    @method_decorator(sensitive_post_parameters())
    def post(self, request, *args, **kwargs):
        if self.password_change_form.is_valid():
            self.password_change_form.save()
            messages.success(request, _("Your password was successfully changed!"))
        return self.get(request, *args, **kwargs)


class BaseProjectDataView(BaseDomainView):
    section_name = ugettext_noop("Data")

    @property
    def section_url(self):
        return reverse('data_interfaces_default', args=[self.domain])


@require_POST
@retry_resource(3)
def keyboard_config(request):
    request.couch_user.keyboard_shortcuts["enabled"] = bool(request.POST.get('enable'))
    request.couch_user.keyboard_shortcuts["main_key"] = request.POST.get('main-key', 'option')
    request.couch_user.save()
    return HttpResponseRedirect(request.GET.get('next'))
