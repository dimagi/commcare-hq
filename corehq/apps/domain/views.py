import datetime
import logging
from couchdbkit import ResourceNotFound
import dateutil
from django.conf import settings
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from corehq import ProjectSettingsTab
from corehq.apps import receiverwrapper
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, Http404

from django.shortcuts import redirect, render
from corehq.apps.domain.calculations import CALCS, CALC_FNS, CALC_ORDER, dom_calc

from corehq.apps.domain.decorators import (domain_admin_required,
    login_required, require_superuser, login_and_domain_required)
from corehq.apps.domain.forms import DomainGlobalSettingsForm,\
    DomainMetadataForm, SnapshotSettingsForm, SnapshotApplicationForm, DomainDeploymentForm, DomainInternalForm
from corehq.apps.domain.models import Domain, LICENSES
from corehq.apps.domain.utils import get_domained_url, normalize_domain_name
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.orgs.models import Organization, OrgRequest, Team
from corehq.apps.commtrack.util import all_sms_codes
from corehq.apps.domain.forms import ProjectSettingsForm
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.django.email import send_HTML_email

from dimagi.utils.web import get_ip, json_response
from corehq.apps.users.decorators import require_can_edit_web_users
from corehq.apps.receiverwrapper.forms import FormRepeaterForm
from corehq.apps.receiverwrapper.models import FormRepeater, CaseRepeater, ShortFormRepeater, AppStructureRepeater
from django.contrib import messages
from django.views.decorators.http import require_POST
import json
from dimagi.utils.post import simple_post
import cStringIO
from PIL import Image
from django.utils.translation import ugettext as _, ugettext_noop


# Domain not required here - we could be selecting it for the first time. See notes domain.decorators
# about why we need this custom login_required decorator
@login_required
def select(request, domain_select_template='domain/select.html'):

    domains_for_user = Domain.active_for_user(request.user)
    if not domains_for_user:
        return redirect('registration_domain')

    return render(request, domain_select_template, {})


class DomainViewMixin(object):
    """
        Paving the way for a world of entirely class-based views.
        Let's do this, guys. :-)
    """

    @property
    @memoized
    def domain(self):
        return self.args[0] if len(self.args) > 0 else self.kwargs.get('domain', "")

    @property
    @memoized
    def domain_object(self):
        try:
            return Domain.get_by_name(self.domain, strict=True)
        except ResourceNotFound:
            raise Http404()


class BaseDomainView(BaseSectionPageView, DomainViewMixin):

    @property
    def main_context(self):
        main_context = super(BaseDomainView, self).main_context
        main_context.update({
            'domain': self.domain,
        })
        return main_context

    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseDomainView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def page_url(self):
        if self.urlname:
            return reverse(self.urlname, args=[self.domain])


class BaseProjectSettingsView(BaseDomainView):
    section_name = ugettext_noop("Project Settings")
    template_name = "settings/base_template.html"

    @property
    def main_context(self):
        main_context = super(BaseProjectSettingsView, self).main_context
        main_context.update({
            'active_tab': ProjectSettingsTab(
                self.request,
                self.urlname,
                domain=self.domain,
                couch_user=self.request.couch_user,
                project=self.request.project
            ),
            'is_project_settings': True,
        })
        return main_context

    @property
    @memoized
    def section_url(self):
        return reverse(EditMyProjectSettingsView.urlname, args=[self.domain])


class DefaultProjectSettingsView(BaseDomainView):
    urlname = 'domain_settings_default'

    def get(self, request, *args, **kwargs):
        if request.couch_user.is_domain_admin(self.domain):
            return HttpResponseRedirect(reverse(EditBasicProjectInfoView.urlname, args=[self.domain]))
        return HttpResponseRedirect(reverse(EditMyProjectSettingsView.urlname, args=[self.domain]))


class BaseAdminProjectSettingsView(BaseProjectSettingsView):
    """
        The base class for all project settings views that require administrative
        access.
    """

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)


class BaseEditProjectInfoView(BaseAdminProjectSettingsView):
    """
        The base class for all the edit project information views.
    """

    @property
    def autocomplete_fields(self):
        return []

    @property
    def main_context(self):
        context = super(BaseEditProjectInfoView, self).main_context
        context.update({
            'autocomplete_fields': self.autocomplete_fields,
            'commtrack_enabled': self.domain_object.commtrack_enabled, # ideally the template gets access to the domain doc through
                # some other means. otherwise it has to be supplied to every view reachable in that sidebar (every
                # view whose template extends users_base.html); mike says he's refactoring all of this imminently, so
                # i will not worry about it until he is done
            'call_center_enabled': self.domain_object.call_center_config.enabled,
            'restrict_superusers': self.domain_object.restrict_superusers,
            'ota_restore_caching': self.domain_object.ota_restore_caching,
        })
        return context


class EditBasicProjectInfoView(BaseEditProjectInfoView):
    template_name = 'domain/admin/info_basic.html'
    urlname = 'domain_basic_info'
    page_title = ugettext_noop("Basic")

    @property
    def can_user_see_meta(self):
        return self.request.couch_user.is_previewer()

    @property
    def autocomplete_fields(self):
        return ['project_type']

    @property
    @memoized
    def basic_info_form(self):
        initial = {
            'default_timezone': self.domain_object.default_timezone,
            'case_sharing': json.dumps(self.domain_object.case_sharing)
        }
        if self.request.method == 'POST':
            if self.can_user_see_meta:
                return DomainMetadataForm(
                    self.request.POST,
                    self.request.FILES,
                    user=self.request.couch_user,
                    domain=self.domain_object.name)
            return DomainGlobalSettingsForm(self.request.POST)

        if self.can_user_see_meta:
            for attr in [
                'project_type',
                'customer_type',
                'commconnect_enabled',
                'survey_management_enabled',
                'sms_case_registration_enabled',
                'sms_case_registration_type',
                'sms_case_registration_owner_id',
                'sms_case_registration_user_id',
                'default_sms_backend_id',
                'commtrack_enabled',
                'restrict_superusers',
                'ota_restore_caching',
                'secure_submissions',
            ]:
                initial[attr] = getattr(self.domain_object, attr)
            initial.update({
                'is_test': self.domain_object.is_test,
                'call_center_enabled': self.domain_object.call_center_config.enabled,
                'call_center_case_owner': self.domain_object.call_center_config.case_owner_id,
                'call_center_case_type': self.domain_object.call_center_config.case_type,
            })

            return DomainMetadataForm(user=self.request.couch_user, domain=self.domain_object.name, initial=initial)
        return DomainGlobalSettingsForm(initial=initial)

    @property
    def page_context(self):
        return {
            'basic_info_form': self.basic_info_form,
        }

    def post(self, request, *args, **kwargs):
        if self.basic_info_form.is_valid():
            if self.basic_info_form.save(request, self.domain_object):
                messages.success(request, _("Project settings saved!"))
            else:
                messages.error(request, _("There seems to have been an error saving your settings. Please try again!"))
        return self.get(request, *args, **kwargs)


class EditDeploymentProjectInfoView(BaseEditProjectInfoView):
    template_name = 'domain/admin/info_deployment.html'
    urlname = 'domain_deployment_info'
    page_title = ugettext_noop("Deployment")

    @property
    def autocomplete_fields(self):
        return ['city', 'country', 'region']

    @property
    @memoized
    def deployment_info_form(self):
        if self.request.method == 'POST':
            return DomainDeploymentForm(self.request.POST)

        initial = {
            'deployment_date': self.domain_object.deployment.date.date if self.domain_object.deployment.date else "",
            'public': 'true' if self.domain_object.deployment.public else 'false',
        }
        for attr in [
            'city',
            'country',
            'region',
            'description',
        ]:
            initial[attr] = getattr(self.domain_object.deployment, attr)
        return DomainDeploymentForm(initial=initial)

    @property
    def page_context(self):
        return {
            'deployment_info_form': self.deployment_info_form,
        }

    def post(self, request, *args, **kwargs):
        if self.deployment_info_form.is_valid():
            if self.deployment_info_form.save(self.domain_object):
                messages.success(request,
                                 _("The deployment information for project %s was successfully updated!")
                                 % self.domain_object.name)
            else:
                messages.error(request, _("There seems to have been an error. Please try again!"))

        return self.get(request, *args, **kwargs)


class EditMyProjectSettingsView(BaseProjectSettingsView):
    template_name = 'domain/admin/my_project_settings.html'
    urlname = 'my_project_settings'
    page_title = ugettext_noop("My Timezone")

    @property
    @memoized
    def my_project_settings_form(self):
        initial = { 'global_timezone': self.domain_object.default_timezone }
        if self.domain_membership:
            initial.update({
                'override_global_tz': self.domain_membership.override_global_tz,
                'user_timezone': (self.domain_membership.timezone if self.domain_membership.override_global_tz
                                  else self.domain_object.default_timezone),
            })
        else:
            initial.update({
                'override_global_tz': False,
                'user_timezone': initial["global_timezone"],
            })

        if self.request.method == 'POST':
            return ProjectSettingsForm(self.request.POST, initial=initial)
        return ProjectSettingsForm(initial=initial)

    @property
    @memoized
    def domain_membership(self):
        return self.request.couch_user.get_domain_membership(self.domain)

    @property
    def page_context(self):
        return {
            'my_project_settings_form': self.my_project_settings_form,
            'override_global_tz': self.domain_membership.override_global_tz if self.domain_membership else False,
            'no_domain_membership': not self.domain_membership,
        }

    def post(self, request, *args, **kwargs):
        if self.my_project_settings_form.is_valid():
            self.my_project_settings_form.save(self.request.couch_user, self.domain)
            messages.success(request, _("Your project settings have been saved!"))
        return self.get(request, *args, **kwargs)


@require_POST
@require_can_edit_web_users
def drop_repeater(request, domain, repeater_id):
    rep = FormRepeater.get(repeater_id)
    rep.retire()
    messages.success(request, "Form forwarding stopped!")
    return HttpResponseRedirect(reverse(DomainForwardingOptionsView.urlname, args=[domain]))

@require_POST
@require_can_edit_web_users
def test_repeater(request, domain):
    url = request.POST["url"]
    form = FormRepeaterForm({"url": url})
    if form.is_valid():
        url = form.cleaned_data["url"]
        # now we fake a post
        fake_post = "<?xml version='1.0' ?><data id='test'><TestString>Test post from CommCareHQ on %s</TestString></data>" \
                    % (datetime.datetime.utcnow())

        try:
            resp = simple_post(fake_post, url)
            if 200 <= resp.status < 300:
                return HttpResponse(json.dumps({"success": True,
                                                "response": resp.read(),
                                                "status": resp.status}))
            else:
                return HttpResponse(json.dumps({"success": False,
                                                "response": resp.read(),
                                                "status": resp.status}))

        except Exception, e:
            errors = str(e)
        return HttpResponse(json.dumps({"success": False, "response": errors}))
    else:
        return HttpResponse(json.dumps({"success": False, "response": "Please enter a valid url."}))


def legacy_domain_name(request, domain, path):
    domain = normalize_domain_name(domain)
    return HttpResponseRedirect(get_domained_url(domain, path))

def autocomplete_fields(request, field):
    prefix = request.GET.get('prefix', '')
    results = Domain.field_by_prefix(field, prefix)
    return HttpResponse(json.dumps(results))

def logo(request, domain):
    logo = Domain.get_by_name(domain).get_custom_logo()
    if logo is None:
        raise Http404()

    return HttpResponse(logo[0], mimetype=logo[1])


class ExchangeSnapshotsView(BaseAdminProjectSettingsView):
    template_name = 'domain/snapshot_settings.html'
    urlname = 'domain_snapshot_settings'
    page_title = ugettext_noop("CommCare Exchange")

    @property
    def page_context(self):
        return {
            'project': self.domain_object,
            'snapshots': list(self.domain_object.snapshots()),
            'published_snapshot': self.domain_object.published_snapshot(),
        }


class CreateNewExchangeSnapshotView(BaseAdminProjectSettingsView):
    template_name = 'domain/create_snapshot.html'
    urlname = 'domain_create_snapshot'
    page_title = ugettext_noop("Publish New Version")

    @property
    def parent_pages(self):
        return [{
            'title': ExchangeSnapshotsView.page_title,
            'url': reverse(ExchangeSnapshotsView.urlname, args=[self.domain]),
        }]

    @property
    def page_context(self):
        context = {
            'form': self.snapshot_settings_form,
            'app_forms': self.app_forms,
            'can_publish_as_org': self.can_publish_as_org,
            'autocomplete_fields': ('project_type', 'phone_model', 'user_type', 'city', 'country', 'region'),
        }
        if self.published_snapshot:
            context.update({
                'published_as_org': self.published_snapshot.publisher == 'organization',
                'author': self.published_snapshot.author,
            })
        elif self.request.method == 'POST':
            context.update({
                'published_as_org': self.request.POST.get('publisher', '') == 'organization',
                'author': self.request.POST.get('author', '')
            })
        return context

    @property
    def can_publish_as_org(self):
        return (self.domain_object.get_organization()
                and self.request.couch_user.is_org_admin(self.domain_object.get_organization().name))

    @property
    @memoized
    def snapshots(self):
        return list(self.domain_object.snapshots())

    @property
    @memoized
    def published_snapshot(self):
        return self.snapshots[0] if self.snapshots else self.domain_object

    @property
    @memoized
    def published_apps(self):
        published_apps = {}
        if self.published_snapshot:
            for app in self.published_snapshot.full_applications():
                base_app_id = app.copy_of if self.domain_object == self.published_snapshot else app.copied_from.copy_of
                published_apps[base_app_id] = app
        return published_apps

    @property
    def app_forms(self):
        app_forms = []
        for app in self.domain_object.applications():
            app = app.get_latest_saved() or app
            if self.request.method == 'POST':
                app_forms.append((app, SnapshotApplicationForm(self.request.POST, prefix=app.id)))
            elif self.published_snapshot and app.copy_of in self.published_apps:
                original = self.published_apps[app.copy_of]
                app_forms.append((app, SnapshotApplicationForm(initial={
                    'publish': True,
                    'name': original.name,
                    'description': original.description,
                    'deployment_date': original.deployment_date,
                    'user_type': original.user_type,
                    'attribution_notes': original.attribution_notes,
                    'phone_model': original.phone_model,

                }, prefix=app.id)))
            else:
                app_forms.append((app,
                                  SnapshotApplicationForm(
                                      initial={
                                          'publish': (self.published_snapshot is None
                                                      or self.published_snapshot == self.domain_object)
                                      }, prefix=app.id)))
        return app_forms

    @property
    @memoized
    def snapshot_settings_form(self):
        if self.request.method == 'POST':
            form = SnapshotSettingsForm(self.request.POST, self.request.FILES)
            form.dom = self.domain_object
            return form

        proj = self.published_snapshot if self.published_snapshot else self.domain_object
        initial = {
            'case_sharing': json.dumps(proj.case_sharing),
            'publish_on_submit': True,
            'share_multimedia': self.published_snapshot.multimedia_included if self.published_snapshot else True,
        }
        init_attribs = ['default_timezone', 'project_type', 'license']
        if self.published_snapshot:
            init_attribs.extend(['title', 'description', 'short_description'])
            if self.published_snapshot.yt_id:
                initial['video'] = 'http://www.youtube.com/watch?v=%s' % self.published_snapshot.yt_id
        for attr in init_attribs:
            initial[attr] = getattr(proj, attr)

        return SnapshotSettingsForm(initial=initial)

    @property
    @memoized
    def has_published_apps(self):
        for app in self.domain_object.applications():
            app = app.get_latest_saved() or app
            if self.request.POST.get("%s-publish" % app.id, False):
                return True
        messages.error(self.request, _("Cannot publish a project without applications to CommCare Exchange"))
        return False

    @property
    def has_signed_eula(self):
        eula_signed = self.request.couch_user.is_eula_signed()
        if not eula_signed:
            messages.error(self.request, _("You must agree to our eula to publish a project to Exchange"))
        return eula_signed

    @property
    def has_valid_form(self):
        is_valid = self.snapshot_settings_form.is_valid()
        if not is_valid:
            messages.error(self.request, _("There are some problems with your form. "
                                           "Please address these issues and try again."))
        return is_valid

    def post(self, request, *args, **kwargs):
        if self.has_published_apps and self.has_signed_eula and self.has_valid_form:
            new_license = request.POST['license']
            if request.POST.get('share_multimedia', False):
                app_ids = self.snapshot_settings_form._get_apps_to_publish()
                media = self.domain_object.all_media(from_apps=app_ids)
                for m_file in media:
                    if self.domain not in m_file.shared_by:
                        m_file.shared_by.append(self.domain)

                    # set the license of every multimedia file that doesn't yet have a license set
                    if not m_file.license:
                        m_file.update_or_add_license(self.domain, type=new_license)

                    m_file.save()

            old = self.domain_object.published_snapshot()
            new_domain = self.domain_object.save_snapshot()
            new_domain.license = new_license
            new_domain.description = request.POST['description']
            new_domain.short_description = request.POST['short_description']
            new_domain.project_type = request.POST['project_type']
            new_domain.title = request.POST['title']
            new_domain.multimedia_included = request.POST.get('share_multimedia', '') == 'on'
            new_domain.publisher = request.POST.get('publisher', None) or 'user'
            if request.POST.get('video'):
                new_domain.yt_id = self.snapshot_settings_form.cleaned_data['video']

            new_domain.author = request.POST.get('author', None)

            new_domain.is_approved = False
            publish_on_submit = request.POST.get('publish_on_submit', "no") == "yes"

            image = self.snapshot_settings_form.cleaned_data['image']
            if image:
                new_domain.image_path = image.name
                new_domain.image_type = image.content_type
            elif request.POST.get('old_image', False):
                new_domain.image_path = old.image_path
                new_domain.image_type = old.image_type
            new_domain.save()

            if publish_on_submit:
                _publish_snapshot(request, self.domain_object, published_snapshot=new_domain)
            else:
                new_domain.published = False
                new_domain.save()

            if image:
                im = Image.open(image)
                out = cStringIO.StringIO()
                im.thumbnail((200, 200), Image.ANTIALIAS)
                im.save(out, new_domain.image_type.split('/')[-1])
                new_domain.put_attachment(content=out.getvalue(), name=image.name)
            elif request.POST.get('old_image', False):
                new_domain.put_attachment(content=old.fetch_attachment(old.image_path), name=new_domain.image_path)

            for application in new_domain.full_applications():
                original_id = application.copied_from._id
                if request.POST.get("%s-publish" % original_id, False):
                    application.name = request.POST["%s-name" % original_id]
                    application.description = request.POST["%s-description" % original_id]
                    date_picked = request.POST["%s-deployment_date" % original_id]
                    try:
                        date_picked = dateutil.parser.parse(date_picked)
                        if date_picked.year > 2009:
                            application.deployment_date = date_picked
                    except Exception:
                        pass
                    #if request.POST.get("%s-name" % original_id):
                    application.phone_model = request.POST["%s-phone_model" % original_id]
                    application.attribution_notes = request.POST["%s-attribution_notes" % original_id]
                    application.user_type = request.POST["%s-user_type" % original_id]

                    if not new_domain.multimedia_included:
                        application.multimedia_map = {}
                    application.save()
                else:
                    application.delete()
            if new_domain is None:
                messages.error(request, _("Version creation failed; please try again"))
            else:
                messages.success(request, (_("Created a new version of your app. This version will be posted to "
                                             "CommCare Exchange pending approval by admins.") if publish_on_submit
                                           else _("Created a new version of your app.")))
                return redirect(ExchangeSnapshotsView.urlname, self.domain)
        return self.get(request, *args, **kwargs)


class ManageProjectMediaView(BaseAdminProjectSettingsView):
    urlname = 'domain_manage_multimedia'
    page_title = ugettext_noop("Multimedia Sharing")
    template_name = 'domain/admin/media_manager.html'

    @property
    def project_media_data(self):
        return [{
            'license': m.license.type if m.license else 'public',
            'shared': self.domain in m.shared_by,
            'url': m.url(),
            'm_id': m._id,
            'tags': m.tags.get(self.domain, []),
            'type': m.doc_type,
        } for m in self.request.project.all_media()]

    @property
    def page_context(self):
        return {
            'media': self.project_media_data,
            'licenses': LICENSES.items(),
        }

    def post(self, request, *args, **kwargs):
        for m_file in request.project.all_media():
            if '%s_tags' % m_file._id in request.POST:
                m_file.tags[self.domain] = request.POST.get('%s_tags' % m_file._id, '').split(' ')

            if self.domain not in m_file.shared_by and request.POST.get('%s_shared' % m_file._id, False):
                m_file.shared_by.append(self.domain)
            elif self.domain in m_file.shared_by and not request.POST.get('%s_shared' % m_file._id, False):
                m_file.shared_by.remove(self.domain)

            if '%s_license' % m_file._id in request.POST:
                m_file.update_or_add_license(self.domain, type=request.POST.get('%s_license' % m_file._id, 'public'))
            m_file.save()
        messages.success(request, _("Multimedia updated successfully!"))
        return self.get(request, *args, **kwargs)


class RepeaterMixin(object):

    @property
    def friendly_repeater_names(self):
        return {
            'FormRepeater': _("Forms"),
            'CaseRepeater': _("Cases"),
            'ShortFormRepeater': _("Form Stubs"),
            'AppStructureRepeater': _("App Schema Changes"),
        }


class DomainForwardingOptionsView(BaseAdminProjectSettingsView, RepeaterMixin):
    urlname = 'domain_forwarding'
    page_title = ugettext_noop("Data Forwarding")
    template_name = 'domain/admin/domain_forwarding.html'

    @property
    def repeaters(self):
        available_repeaters = [
            FormRepeater, CaseRepeater, ShortFormRepeater, AppStructureRepeater,
        ]
        return [(r.__name__, r.by_domain(self.domain), self.friendly_repeater_names[r.__name__])
                for r in available_repeaters]

    @property
    def page_context(self):
        return {
            'repeaters': self.repeaters,
        }


class AddRepeaterView(BaseAdminProjectSettingsView, RepeaterMixin):
    urlname = 'add_repeater'
    page_title = ugettext_noop("Forward Data")
    template_name = 'domain/admin/add_form_repeater.html'

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
        return "Forward %s" % self.friendly_repeater_names.get(self.repeater_type, "Data")

    @property
    @memoized
    def repeater_class(self):
        try:
            return receiverwrapper.models.repeater_types[self.repeater_type]
        except KeyError:
            raise Http404()

    @property
    @memoized
    def add_repeater_form(self):
        if self.request.method == 'POST':
            return FormRepeaterForm(self.request.POST)
        return FormRepeaterForm()

    @property
    def page_context(self):
        return {
            'form': self.add_repeater_form,
            'repeater_type': self.repeater_type,
        }

    def post(self, request, *args, **kwargs):
        if self.add_repeater_form.is_valid():
            repeater = self.repeater_class(
                domain=self.domain,
                url=self.add_repeater_form.cleaned_data['url']
            )
            repeater.save()
            messages.success(request, _("Forwarding set up to %s" % repeater.url))
            return HttpResponseRedirect(reverse(DomainForwardingOptionsView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)

class OrgSettingsView(BaseAdminProjectSettingsView):
    template_name = 'domain/orgs_settings.html'
    urlname = 'domain_org_settings'
    page_title = ugettext_noop("Organization")

    @property
    def page_context(self):
        domain = self.domain_object
        org_users = []
        teams = Team.get_by_domain(domain.name)
        for team in teams:
            for user in team.get_members():
                user.team_id = team.get_id
                user.team = team.name
                org_users.append(user)

        for user in org_users:
            user.current_domain = domain.name

        all_orgs = Organization.get_all()

        return {
            "project": domain,
            'domain': domain.name,
            "organization": Organization.get_by_name(getattr(domain, "organization", None)),
            "org_users": org_users,
            "all_orgs": all_orgs,
        }


class BaseInternalDomainSettingsView(BaseProjectSettingsView):

    @method_decorator(login_and_domain_required)
    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseInternalDomainSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        context = super(BaseInternalDomainSettingsView, self).main_context
        context.update({
            'project': self.domain_object,
        })
        return context

    @property
    def page_name(self):
        return mark_safe("%s <small>Internal</small>" % self.page_title)


class EditInternalDomainInfoView(BaseInternalDomainSettingsView):
    urlname = 'domain_internal_settings'
    page_title = ugettext_noop("Project Information")
    template_name = 'domain/internal_settings.html'

    @property
    @memoized
    def internal_settings_form(self):
        if self.request.method == 'POST':
            return DomainInternalForm(self.request.POST)
        initial = {}
        internal_attrs = [
            'sf_contract_id',
            'sf_account_id',
            'commcare_edition',
            'services',
            'initiative',
            'workshop_region',
            'project_state',
            'area',
            'sub_area',
            'organization_name',
            'notes',
            'platform',
            'self_started',
            'using_adm',
            'using_call_center',
            'custom_eula',
            'can_use_data',
            'project_manager',
            'phone_model',
        ]
        for attr in internal_attrs:
            val = getattr(self.domain_object.internal, attr)
            if isinstance(val, bool):
                val = 'true' if val else 'false'
            initial[attr] = val
        return DomainInternalForm(initial=initial)

    @property
    def page_context(self):
        return {
            'project': self.domain_object,
            'form': self.internal_settings_form,
            'areas': dict([(a["name"], a["sub_areas"]) for a in settings.INTERNAL_DATA["area"]]),
        }

    def post(self, request, *args, **kwargs):
        if self.internal_settings_form.is_valid():
            self.internal_settings_form.save(self.domain_object)
            messages.success(request, _("The internal information for project %s was successfully updated!")
                                      % self.domain)
        else:
            messages.error(request, _("There seems to have been an error. Please try again!"))
        return self.get(request, *args, **kwargs)


class EditInternalCalculationsView(BaseInternalDomainSettingsView):
    urlname = 'domain_internal_calculations'
    page_title = ugettext_noop("Calculated Properties")
    template_name = 'domain/internal_calculations.html'

    @property
    def page_context(self):
        return {
            'calcs': CALCS,
            'order': CALC_ORDER,
        }


@login_and_domain_required
@require_superuser
def calculated_properties(request, domain):
    calc_tag = request.GET.get("calc_tag", '').split('--')
    extra_arg = calc_tag[1] if len(calc_tag) > 1 else ''
    calc_tag = calc_tag[0]

    if not calc_tag or calc_tag not in CALC_FNS.keys():
        data = {"error": 'This tag does not exist'}
    else:
        data = {"value": dom_calc(calc_tag, domain, extra_arg)}
    return json_response(data)


def _publish_snapshot(request, domain, published_snapshot=None):
    snapshots = domain.snapshots()
    for snapshot in snapshots:
        if snapshot.published:
            snapshot.published = False
            if not published_snapshot or snapshot.name != published_snapshot.name:
                snapshot.save()
    if published_snapshot:
        if published_snapshot.copied_from.name != domain.name:
            messages.error(request, "Invalid snapshot")
            return False

        # cda stuff. In order to publish a snapshot, a user must have agreed to this
        published_snapshot.cda.signed = True
        published_snapshot.cda.date = datetime.datetime.utcnow()
        published_snapshot.cda.type = 'Content Distribution Agreement'
        if request.couch_user:
            published_snapshot.cda.user_id = request.couch_user.get_id
        published_snapshot.cda.user_ip = get_ip(request)

        published_snapshot.published = True
        published_snapshot.save()
        _notification_email_on_publish(domain, published_snapshot, request.couch_user)
    return True

def _notification_email_on_publish(domain, snapshot, published_by):
    url_base = Site.objects.get_current().domain
    params = {"domain": domain, "snapshot": snapshot, "published_by": published_by, "url_base": url_base}
    text_content = render_to_string("domain/email/published_app_notification.txt", params)
    html_content = render_to_string("domain/email/published_app_notification.html", params)
    recipients = settings.EXCHANGE_NOTIFICATION_RECIPIENTS
    subject = "New App on Exchange: %s" % snapshot.title
    try:
        for recipient in recipients:
            send_HTML_email(subject, recipient, html_content, text_content=text_content,
                            email_from=settings.DEFAULT_FROM_EMAIL)
    except Exception:
        logging.warning("Can't send notification email, but the message was:\n%s" % text_content)

@domain_admin_required
def set_published_snapshot(request, domain, snapshot_name=''):
    domain = request.project
    snapshots = domain.snapshots()
    if request.method == 'POST':
        if snapshot_name != '':
            published_snapshot = Domain.get_by_name(snapshot_name)
            _publish_snapshot(request, domain, published_snapshot=published_snapshot)
        else:
            _publish_snapshot(request, domain)
    return redirect('domain_snapshot_settings', domain.name)


class BaseCommTrackAdminView(BaseAdminProjectSettingsView):

    @property
    @memoized
    def commtrack_settings(self):
        return self.domain_object.commtrack_settings


class BasicCommTrackSettingsView(BaseCommTrackAdminView):
    urlname = 'domain_commtrack_settings'
    page_title = ugettext_noop("Basic CommTrack Settings")
    template_name = 'domain/admin/commtrack_settings.html'

    @property
    def page_context(self):
        return {
            'other_sms_codes': dict(self.get_other_sms_codes()),
            'settings': self.settings_context,
        }

    @property
    def settings_context(self):
        return {
            'keyword': self.commtrack_settings.multiaction_keyword,
            'actions': [self._get_action_info(a) for a in self.commtrack_settings.actions],
            'loc_types': [self._get_loctype_info(l) for l in self.commtrack_settings.location_types],
            'requisition_config': {
                'enabled': self.commtrack_settings.requisition_config.enabled,
                'actions': [self._get_action_info(a) for a in self.commtrack_settings.requisition_config.actions],
            },
            'openlmis_config': self.commtrack_settings.openlmis_config._doc,
        }

    def _get_loctype_info(self, loctype):
        return {
            'name': loctype.name,
            'allowed_parents': [p or None for p in loctype.allowed_parents],
            'administrative': loctype.administrative,
        }

    def _get_action_info(self, action):
        return {
            'type': action.action_type,
            'keyword': action.keyword,
            'name': action.action_name,
            'caption': action.caption,
        }

    def get_other_sms_codes(self):
        for k, v in all_sms_codes(self.domain).iteritems():
            if v[0] == 'product':
                yield (k, (v[0], v[1].name))

    def post(self, request, *args, **kwargs):
        from corehq.apps.commtrack.models import CommtrackActionConfig, LocationType

        payload = json.loads(request.POST.get('json'))

        self.commtrack_settings.multiaction_keyword = payload['keyword']

        def make_action_name(caption, actions):
            existing = filter(None, [a.get('name') for a in actions])
            name = ''.join(c.lower() if c.isalpha() else '_' for c in caption)
            disambig = 1

            def _name():
                return name + ('_%s' % disambig if disambig > 1 else '')

            while _name() in existing:
                disambig += 1

            return _name()

        def mk_action(action):
            action['action_type'] = action['type']
            del action['type']

            if not action.get('name'):
                action['name'] = make_action_name(action['caption'], payload['actions'])

            return CommtrackActionConfig(**action)

        def mk_loctype(loctype):
            loctype['allowed_parents'] = [p or '' for p in loctype['allowed_parents']]
            return LocationType(**loctype)

        #TODO add server-side input validation here (currently validated on client)

        self.commtrack_settings.actions = [mk_action(a) for a in payload['actions']]
        self.commtrack_settings.location_types = [mk_loctype(l) for l in payload['loc_types']]
        self.commtrack_settings.requisition_config.enabled = payload['requisition_config']['enabled']
        self.commtrack_settings.requisition_config.actions =  [mk_action(a) for a in payload['requisition_config']['actions']]

        if 'openlmis_config' in payload:
            for item in payload['openlmis_config']:
                setattr(self.commtrack_settings.openlmis_config, item, payload['openlmis_config'][item])

        self.commtrack_settings.save()

        return self.get(request, *args, **kwargs)


class AdvancedCommTrackSettingsView(BaseCommTrackAdminView):
    urlname = 'commtrack_settings_advanced'
    page_title = ugettext_noop("Advanced CommTrack Settings")
    template_name = 'domain/admin/commtrack_settings_advanced.html'

    @property
    def page_context(self):
        return {
            'form': self.commtrack_settings_form
        }

    @property
    @memoized
    def commtrack_settings_form(self):
        from corehq.apps.commtrack.forms import AdvancedSettingsForm
        initial = self.commtrack_settings.to_json()
        initial.update(dict(('consumption_' + k, v) for k, v in
            self.commtrack_settings.consumption_config.to_json().items()))
        initial.update(dict(('stock_' + k, v) for k, v in
            self.commtrack_settings.stock_levels_config.to_json().items()))

        if self.request.method == 'POST':
            return AdvancedSettingsForm(self.request.POST, initial=initial)
        return AdvancedSettingsForm(initial=initial)

    def post(self, request, *args, **kwargs):
        if self.commtrack_settings_form.is_valid():
            data = self.commtrack_settings_form.cleaned_data
            self.commtrack_settings.use_auto_consumption = bool(data.get('use_auto_consumption'))

            fields = ('emergency_level', 'understock_threshold', 'overstock_threshold')
            for field in fields:
                if data.get('stock_' + field):
                    setattr(self.commtrack_settings.stock_levels_config, field,
                            data['stock_' + field])

            consumption_fields = ('min_periods', 'min_window', 'window')
            for field in consumption_fields:
                if data.get('consumption_' + field):
                    setattr(self.commtrack_settings.consumption_config, field,
                            data['consumption_' + field])

            self.commtrack_settings.save()
            messages.success(request, _("Settings updated!"))
            return HttpResponseRedirect(self.page_url)
        return self.get(request, *args, **kwargs)


@require_POST
@domain_admin_required
def org_request(request, domain):
    org_name = request.POST.get("org_name", None)
    org = Organization.get_by_name(org_name)
    if org:
        org_request = OrgRequest.get_requests(org_name, domain=domain, user_id=request.couch_user.get_id)
        if not org_request:
            org_request = OrgRequest(organization=org_name, domain=domain,
                requested_by=request.couch_user.get_id, requested_on=datetime.datetime.utcnow())
            org_request.save()
            _send_request_notification_email(request, org, domain)
            messages.success(request,
                "Your request was submitted. The admin of organization %s can now choose to manage the project %s" %
                (org_name, domain))
        else:
            messages.error(request, "You've already submitted a request to this organization")
    else:
        messages.error(request, "The organization '%s' does not exist" % org_name)
    return HttpResponseRedirect(reverse('domain_org_settings', args=[domain]))

def _send_request_notification_email(request, org, dom):
    url_base = Site.objects.get_current().domain
    params = {"org": org, "dom": dom, "requestee": request.couch_user, "url_base": url_base}
    text_content = render_to_string("domain/email/org_request_notification.txt", params)
    html_content = render_to_string("domain/email/org_request_notification.html", params)
    recipients = [member.email for member in org.get_members() if member.is_org_admin(org.name)]
    subject = "New request to add a project to your organization! -- CommcareHQ"
    try:
        for recipient in recipients:
            send_HTML_email(subject, recipient, html_content, text_content=text_content,
                            email_from=settings.DEFAULT_FROM_EMAIL)
    except Exception:
        logging.warning("Can't send notification email, but the message was:\n%s" % text_content)
