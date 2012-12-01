import datetime
import dateutil
from corehq.apps import receiverwrapper
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, Http404

from django.shortcuts import redirect

from corehq.apps.domain.decorators import REDIRECT_FIELD_NAME, login_required_late_eval_of_LOGIN_URL, login_and_domain_required, domain_admin_required
from corehq.apps.domain.forms import DomainGlobalSettingsForm,\
    DomainMetadataForm, SnapshotSettingsForm, SnapshotApplicationForm, DomainDeploymentForm
from corehq.apps.domain.models import Domain, LICENSES
from corehq.apps.domain.utils import get_domained_url, normalize_domain_name
from corehq.apps.users.models import CouchUser

from dimagi.utils.web import render_to_response, get_ip
from corehq.apps.users.views import require_can_edit_web_users
from corehq.apps.receiverwrapper.forms import FormRepeaterForm
from corehq.apps.receiverwrapper.models import FormRepeater, CaseRepeater, ShortFormRepeater
from django.contrib import messages
from django.views.decorators.http import require_POST
import json
from dimagi.utils.post import simple_post
import cStringIO
from PIL import Image
from django.utils.translation import ugettext as _


# Domain not required here - we could be selecting it for the first time. See notes domain.decorators
# about why we need this custom login_required decorator
from lib.django_user_registration.models import RegistrationProfile

@login_required_late_eval_of_LOGIN_URL
def select(request, domain_select_template='domain/select.html'):

    domains_for_user = Domain.active_for_user(request.user)
    if not domains_for_user:
        return redirect('registration_domain')

    return render_to_response(request, domain_select_template, {})


########################################################################################################

def _bool_to_yes_no( b ):
    return 'Yes' if b else 'No'

########################################################################################################

def _dict_for_one_user( user, domain ):
    retval = dict( id = user.id,
                   username = user.username,
                   first_name = user.first_name,
                   last_name = user.last_name,
                   is_active_auth = _bool_to_yes_no(user.is_active),
                   last_login = user.last_login )

    is_active_member = user.domain_membership.filter(domain = domain)[0].is_active
    retval['is_active_member'] = _bool_to_yes_no(is_active_member)

    # TODO: update this to use new couch user permissions scheme
    # ct = ContentType.objects.get_for_model(Domain)
    # is_domain_admin = user.permission_set.filter(content_type = ct,
    #                                             object_id = domain.id,
    #                                             name=Permissions.ADMINISTRATOR)
    # retval['is_domain_admin'] = _bool_to_yes_no(is_domain_admin)
    retval['is_domain_admin'] = False

    # user is a unique get in the registrationprofile table; there can be at most
    # one invite per user, so if there is any invite at all, it's safe to just grab
    # the zero-th one
    invite_status = user.registrationprofile_set.all()
    if invite_status:
        if invite_status[0].activation_key == RegistrationProfile.ACTIVATED:
            val = 'Activated'
        else:
            val = 'Not activated'
    else:
        val = 'Admin added'
    retval['invite_status'] = val

    return retval

@require_can_edit_web_users
def domain_forwarding(request, domain):
    form_repeaters = FormRepeater.by_domain(domain)
    case_repeaters = CaseRepeater.by_domain(domain)
    short_form_repeaters = ShortFormRepeater.by_domain(domain)
    return render_to_response(request, "domain/admin/domain_forwarding.html", {
        "domain": domain,
        "repeaters": (
            ("FormRepeater", form_repeaters),
            ("CaseRepeater", case_repeaters),
            ("ShortFormRepeater", short_form_repeaters)
        ),
    })

@require_POST
@require_can_edit_web_users
def drop_repeater(request, domain, repeater_id):
    rep = FormRepeater.get(repeater_id)
    rep.retire()
    messages.success(request, "Form forwarding stopped!")
    return HttpResponseRedirect(reverse("corehq.apps.domain.views.domain_forwarding", args=[domain]))

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


@require_can_edit_web_users
def add_repeater(request, domain, repeater_type):
    if request.method == "POST":
        form = FormRepeaterForm(request.POST)
        try:
            cls = receiverwrapper.models.repeater_types[repeater_type]
        except KeyError:
            raise Http404()
        if form.is_valid():
            repeater = cls(domain=domain, url=form.cleaned_data["url"])
            repeater.save()
            messages.success(request, "Forwarding setup to %s" % repeater.url)
            return HttpResponseRedirect(reverse("corehq.apps.domain.views.domain_forwarding", args=[domain]))
    else:
        form = FormRepeaterForm()
    return render_to_response(request, "domain/admin/add_form_repeater.html", {
        "domain": domain,
        "form": form,
        "repeater_type": repeater_type,
    })

def legacy_domain_name(request, domain, path):
    domain = normalize_domain_name(domain)
    return HttpResponseRedirect(get_domained_url(domain, path))

@domain_admin_required
def project_settings(request, domain, template="domain/admin/project_settings.html"):
    class _NeverFailForm(object):
            def is_valid(self):              return True
            def save(self, request, domain): return True
    domain = Domain.get_by_name(domain)
    user_sees_meta = request.couch_user.is_previewer()

    if request.method == "POST" and \
       'billing_info_form' not in request.POST and \
       'deployment_info_form' not in request.POST:
        # deal with saving the settings data
        if user_sees_meta:
            form = DomainMetadataForm(request.POST)
        else:
            form = DomainGlobalSettingsForm(request.POST)
        if form.is_valid():
            if form.save(request, domain):
                messages.success(request, "Project settings saved!")
            else:
                messages.error(request, "There seems to have been an error saving your settings. Please try again!")
    else:
        if user_sees_meta:
            form = DomainMetadataForm(initial={
                'default_timezone': domain.default_timezone,
                'case_sharing': json.dumps(domain.case_sharing),
                'project_type': domain.project_type,
                'customer_type': domain.customer_type,
                'is_test': json.dumps(domain.is_test),
            })
        else:
            form = DomainGlobalSettingsForm(initial={
                'default_timezone': domain.default_timezone,
                'case_sharing': json.dumps(domain.case_sharing)
                })

    if request.method == 'POST' and 'deployment_info_form' in request.POST:
        deployment_form = DomainDeploymentForm(request.POST)
        if deployment_form.is_valid():
            if deployment_form.save(domain):
                messages.success(request, "The deployment information for project %s was successfully updated!" % domain.name)
            else:
                messages.error(request, "There seems to have been an error. Please try again!")
    else:
        deployment_form = DomainDeploymentForm(initial={
            'city': domain.deployment.city,
            'country': domain.deployment.country,
            'region': domain.deployment.region,
            'deployment_date': domain.deployment.date.date if domain.deployment.date else "",
            'description': domain.deployment.description,
            'public': 'true' if domain.deployment.public else 'false'
        })

    try:
        from hqbilling.forms import DomainBillingInfoForm
        # really trying to make corehq not dependent on hqbilling here
        if request.method == 'POST' and 'billing_info_form' in request.POST:
            billing_info_form = DomainBillingInfoForm(request.POST)
            if billing_info_form.is_valid():
                billing_info_form.save(domain)
                messages.info(request, "The billing address for project %s was successfully updated!" % domain.name)
        else:
            initial = dict(phone_number=domain.billing_number, currency_code=domain.currency_code)
            initial.update(domain.billing_address._doc)
            billing_info_form = DomainBillingInfoForm(initial=initial)
        billing_info_partial = 'hqbilling/domain/forms/billing_info.html'
        billing_enabled=True
    except ImportError:
        billing_enabled=False
        billing_info_form = None
        billing_info_partial = None


    return render_to_response(request, template, dict(
        domain=domain.name,
        form=form,
        deployment_form=deployment_form,
        languages=domain.readable_languages(),
        applications=domain.applications(),
        autocomplete_fields=('project_type', 'phone_model', 'user_type', 'city', 'country', 'region'),
        billing_info_form=billing_info_form,
        billing_info_partial=billing_info_partial,
        billing_enabled=billing_enabled
    ))

def autocomplete_fields(request, field):
    prefix = request.GET.get('prefix', '')
    results = Domain.field_by_prefix(field, prefix)
    return HttpResponse(json.dumps(results))

@domain_admin_required
def snapshot_settings(request, domain):
    domain = Domain.get_by_name(domain)
    snapshots = domain.snapshots()
    return render_to_response(request, 'domain/snapshot_settings.html',
                {"project": domain, 'domain': domain.name, 'snapshots': list(snapshots), 'published_snapshot': domain.published_snapshot()})

@domain_admin_required
def create_snapshot(request, domain):
    domain = Domain.get_by_name(domain)
    #latest_applications = [app.get_latest_saved() or app for app in domain.applications()]
    if request.method == 'GET':
        form = SnapshotSettingsForm(initial={
                'default_timezone': domain.default_timezone,
                'case_sharing': json.dumps(domain.case_sharing),
                'project_type': domain.project_type,
                'share_multimedia': True,
                'license': domain.license,
                'publish_on_submit': True,
            })
        snapshots = list(domain.snapshots())
        published_snapshot = snapshots[0] if snapshots else domain
        published_apps = {}
        if published_snapshot is not None:
            form = SnapshotSettingsForm(initial={
                'default_timezone': published_snapshot.default_timezone,
                'case_sharing': json.dumps(published_snapshot.case_sharing),
                'project_type': published_snapshot.project_type,
                'license': published_snapshot.license,
                'title': published_snapshot.title,
                'author': published_snapshot.author,
                'share_multimedia': published_snapshot.multimedia_included,
                'description': published_snapshot.description,
                'short_description': published_snapshot.short_description,
                'publish_on_submit': True,
            })
            for app in published_snapshot.full_applications():
                if domain == published_snapshot:
                    published_apps[app._id] = app
                else:
                    published_apps[app.copied_from._id] = app
        app_forms = []
        for app in domain.applications():
            app = app.get_latest_saved() or app
            if published_snapshot and app._id in published_apps:
                original = published_apps[app._id]
                app_forms.append((app, SnapshotApplicationForm(initial={
                    'publish': True,
                    'name': original.name,
                    'description': original.description,
                    'short_description': original.short_description,
                    'deployment_date': original.deployment_date,
                    'user_type': original.user_type,
                    'attribution_notes': original.attribution_notes,
                    'phone_model': original.phone_model,

                }, prefix=app.id)))
            else:
                app_forms.append((app, SnapshotApplicationForm(initial={'publish': (published_snapshot is None or published_snapshot == domain)}, prefix=app.id)))
        return render_to_response(request, 'domain/create_snapshot.html',
            {'domain': domain.name,
             'form': form,
             #'latest_applications': latest_applications,
             'app_forms': app_forms,
             'autocomplete_fields': ('project_type', 'phone_model', 'user_type', 'city', 'country', 'region')})
    elif request.method == 'POST':
        form = SnapshotSettingsForm(request.POST, request.FILES)
        form.dom = domain
        app_forms = []
        publishing_apps = False
        for app in domain.applications():
            app = app.get_latest_saved() or app
            app_forms.append((app, SnapshotApplicationForm(request.POST, prefix=app.id)))
            publishing_apps = publishing_apps or request.POST.get("%s-publish" % app.id, False)
        if not publishing_apps:
            messages.error(request, "Cannot publish a project without applications to CommCare Exchange")
            return render_to_response(request, 'domain/create_snapshot.html',
                {'domain': domain.name,
                 'form': form,
                 'app_forms': app_forms,
                 'autocomplete_fields': ('project_type', 'phone_model', 'user_type', 'city', 'country', 'region')})

        current_user = request.couch_user
        if not current_user.is_eula_signed():
            messages.error(request, 'You must agree to our eula to publish a project to Exchange')
            return render_to_response(request, 'domain/create_snapshot.html',
                {'domain': domain.name,
                 'form': form,
                 'app_forms': app_forms,
                 'autocomplete_fields': ('project_type', 'phone_model', 'user_type', 'city', 'country', 'region')})

        if not form.is_valid():
            messages.error(request, _("There are some problems with your form. Please address these issues and try again."))
            return render_to_response(request, 'domain/create_snapshot.html',
                    {'domain': domain.name,
                     'form': form,
                     #'latest_applications': latest_applications,
                     'app_forms': app_forms,
                     'autocomplete_fields': ('project_type', 'phone_model', 'user_type', 'city', 'country', 'region')})

        new_license = request.POST['license']
        if request.POST.get('share_multimedia', False):
            app_ids = form._get_apps_to_publish()
            media = domain.all_media(from_apps=app_ids)
            for m_file in media:
                if domain.name not in m_file.shared_by:
                    m_file.shared_by.append(domain.name)

                # set the license of every multimedia file that doesn't yet have a license set
                if not m_file.license:
                    m_file.update_or_add_license(domain.name, type=new_license)

                m_file.save()

        old = domain.published_snapshot()
        new_domain = domain.save_snapshot()
        new_domain.license = new_license
        new_domain.description = request.POST['description']
        new_domain.short_description = request.POST['short_description']
        new_domain.project_type = request.POST['project_type']
        new_domain.title = request.POST['title']
        new_domain.author = request.POST['author']
        new_domain.multimedia_included = request.POST.get('share_multimedia', '') == 'on'

        new_domain.is_approved = False
        publish_on_submit = request.POST.get('publish_on_submit', False)

        image = form.cleaned_data['image']
        if image:
            new_domain.image_path = image.name
            new_domain.image_type = image.content_type
        elif request.POST.get('old_image', False):
            new_domain.image_path = old.image_path
            new_domain.image_type = old.image_type
        new_domain.save()

        if publish_on_submit:
            publish_snapshot(request, domain, published_snapshot=new_domain)
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
                application.short_description = request.POST["%s-short_description" % original_id]
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
                    application.multimedia_map = None
                application.save()
            else:
                application.delete()

        if new_domain is None:
            return render_to_response(request, 'domain/snapshot_settings.html',
                    {'domain': domain.name,
                     'form': form,
                     #'latest_applications': latest_applications,
                     'app_forms': app_forms,
                     'error_message': _('Version creation failed; please try again')})

        if publish_on_submit:
            messages.success(request, _("Created a new version of your app. This version will be posted to CommCare Exchange pending approval by admins."))
        else:
            messages.success(request, _("Created a new version of your app."))
        return redirect('domain_snapshot_settings', domain.name)

def publish_snapshot(request, domain, published_snapshot=None):
    snapshots = domain.snapshots()
    for snapshot in snapshots:
        if snapshot.published:
            snapshot.published = False
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
    return True

@domain_admin_required
def set_published_snapshot(request, domain, snapshot_name=''):
    domain = request.project
    snapshots = domain.snapshots()
    if request.method == 'POST':
        if snapshot_name != '':
            published_snapshot = Domain.get_by_name(snapshot_name)
            publish_snapshot(request, domain, published_snapshot=published_snapshot)
        else:
            publish_snapshot(request, domain)
    return redirect('domain_snapshot_settings', domain.name)

@domain_admin_required
def manage_multimedia(request, domain):
    media = request.project.all_media()
    if request.method == "POST":
        for m_file in media:
            if '%s_tags' % m_file._id in request.POST:
                m_file.tags[domain] = request.POST.get('%s_tags' % m_file._id, '').split(' ')

            if domain not in m_file.shared_by and request.POST.get('%s_shared' % m_file._id, False):
                m_file.shared_by.append(domain)
            elif domain in m_file.shared_by and not request.POST.get('%s_shared' % m_file._id, False):
                m_file.shared_by.remove(domain)

            if '%s_license' % m_file._id in request.POST:
                m_file.update_or_add_license(domain, type=request.POST.get('%s_license' % m_file._id, 'public'))
            m_file.save()
        messages.success(request, "Multimedia updated successfully!")

    return render_to_response(request, 'domain/admin/media_manager.html', {'domain': domain,
        'media': [{
            'license': m.license.type if m.license else 'public',
            'shared': domain in m.shared_by,
            'url': m.url(),
            'm_id': m._id,
            'tags': m.tags.get(domain, []),
            'type': m.doc_type
                   } for m in media],
        'licenses': LICENSES.items()
                                                                     })
