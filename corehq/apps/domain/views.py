import datetime
from django.contrib.auth.views import password_reset_confirm
from django.views.decorators.csrf import csrf_protect
from corehq.apps import receiverwrapper
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, Http404, HttpResponseForbidden

from django_tables import tables
from django.shortcuts import redirect

from corehq.apps.domain.decorators import REDIRECT_FIELD_NAME, login_required_late_eval_of_LOGIN_URL, login_and_domain_required, domain_admin_required, require_previewer
from corehq.apps.domain.forms import DomainSelectionForm, DomainGlobalSettingsForm,\
    DomainMetadataForm, SnapshotSettingsForm
from corehq.apps.domain.models import Domain, LICENSES
from corehq.apps.domain.utils import get_domained_url, normalize_domain_name

from dimagi.utils.web import render_to_response, json_response
from corehq.apps.users.views import require_can_edit_web_users
from corehq.apps.receiverwrapper.forms import FormRepeaterForm
from corehq.apps.receiverwrapper.models import FormRepeater, CaseRepeater
from django.contrib import messages
from django.views.decorators.http import require_POST
import json
from dimagi.utils.post import simple_post
from corehq.apps.registration.forms import DomainRegistrationForm
from django.forms.widgets import Select

# Domain not required here - we could be selecting it for the first time. See notes domain.decorators
# about why we need this custom login_required decorator
from lib.django_user_registration.models import RegistrationProfile

@login_required_late_eval_of_LOGIN_URL
def select( request, 
            redirect_field_name = REDIRECT_FIELD_NAME,
            domain_select_template = 'domain/select.html' ):
    
    domains_for_user = Domain.active_for_user(request.user)
    if not domains_for_user:
        return redirect('registration_domain')
    
    redirect_to = request.REQUEST.get(redirect_field_name, '')    
    if request.method == 'POST': # If the form has been submitted...        
        form = DomainSelectionForm(domain_list=domains_for_user,
                                   data=request.POST) # A form bound to the POST data
                     
        if form.is_valid():
            # We've just checked the submitted data against a freshly-retrieved set of domains
            # associated with the user. It's safe to set the domain in the sesssion (and we'll
            # check again on views validated with the domain-checking decorator)
            form.save(request) # Needs request because it saves domain in session
    
            #  Weak attempt to give user a good UX - make sure redirect_to isn't garbage.
            domain = form.cleaned_data['domain_list'].name
            if not redirect_to or '//' in redirect_to or ' ' in redirect_to:
                redirect_to = reverse('domain_homepage', args=[domain])
            return HttpResponseRedirect(redirect_to) # Redirect after POST
    else:
        # An unbound form
        form = DomainSelectionForm( domain_list=domains_for_user ) 

    vals = dict( next = redirect_to,
                 form = form )

    return render_to_response(request, domain_select_template, vals)

########################################################################################################

########################################################################################################
        
class UserTable(tables.Table):
    id = tables.Column(verbose_name="Id")
    username = tables.Column(verbose_name="Username")
    first_name = tables.Column(verbose_name="First name")
    last_name = tables.Column(verbose_name="Last name")
    is_active_auth = tables.Column(verbose_name="Active in system")
    is_active_member = tables.Column(verbose_name="Active in domain")
    is_domain_admin = tables.Column(verbose_name="Domain admin")
    last_login = tables.Column(verbose_name="Most recent login")
    invite_status = tables.Column(verbose_name="Invite status")    
        
########################################################################################################        

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
    return render_to_response(request, "domain/admin/domain_forwarding.html", {
        "domain": domain,
        "repeaters": (
            ("FormRepeater", form_repeaters),
            ("CaseRepeater", case_repeaters)
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
    if request.method == "POST":
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
                'city': domain.city,
                'country': domain.country,
                'region': domain.region,
                'project_type': domain.project_type,
                'customer_type': domain.customer_type,
                'is_test': json.dumps(domain.is_test),
                'description': domain.description,
                'is_shared': domain.is_shared,
                'license': domain.license
            })
        else:
            form = DomainGlobalSettingsForm(initial={
                'default_timezone': domain.default_timezone,
                'case_sharing': json.dumps(domain.case_sharing),

                })
        
    return render_to_response(request, template, {
        "domain": domain.name,
        "form": form,
        "languages": domain.readable_languages(),
        "applications": domain.applications(),
        'autocomplete_fields': ('project_type', 'phone_model', 'user_type', 'city', 'country', 'region')
    })

def autocomplete_fields(request, field):
    prefix = request.GET.get('prefix', '')
    results = Domain.field_by_prefix(field, prefix)
    return HttpResponse(json.dumps(results))

@domain_admin_required
def snapshot_settings(request, domain):
    domain = Domain.get_by_name(domain)
    snapshots = domain.snapshots()
    return render_to_response(request, 'domain/snapshot_settings.html',
                {'domain': domain.name, 'snapshots': snapshots})

@domain_admin_required
def create_snapshot(request, domain):
    domain = Domain.get_by_name(domain)
    form = SnapshotSettingsForm()
    latest_applications = [app.get_latest_saved() or app for app in domain.applications()]
    if request.method == 'GET':
        return render_to_response(request, 'domain/create_snapshot.html',
            {'domain': domain.name,
             'form': form,
             'latest_applications': latest_applications,
             'autocomplete_fields': ('project_type', 'phone_model', 'user_type', 'city', 'country', 'region')})
    elif request.method == 'POST':
        form = SnapshotSettingsForm(request.POST)
        if not form.is_valid():
            return render_to_response(request, 'domain/create_snapshot.html',
                    {'domain': domain.name,
                     'form': form})
        new_domain = domain.save_snapshot()
        if request.POST['license'] in LICENSES.keys():
            new_domain.license = request.POST['license']
        new_domain.description = request.POST['description']
        new_domain.attribution_notes = request.POST['attribution_notes']
        new_domain.project_type = request.POST['project_type']
        new_domain.region = request.POST['region']
        new_domain.city = request.POST['city']
        new_domain.country = request.POST['country']
        if int(request.POST['deployment_date_year']) > 2009 and request.POST['deployment_date_month'] and request.POST['deployment_date_day']:
            new_domain.deployment_date = datetime.datetime(int(request.POST['deployment_date_year']), int(request.POST['deployment_date_month']), int(request.POST['deployment_date_day']))
        new_domain.phone_model = request.POST['phone_model']
        new_domain.user_type = request.POST['user_type']
        new_domain.title = request.POST['title']
        new_domain.author = request.POST['author']
        for snapshot in domain.snapshots():
            if snapshot.published and snapshot._id != new_domain._id:
                snapshot.published = False
                snapshot.save()
        new_domain.is_approved = False
        new_domain.published = True
        new_domain.save()

        for application in new_domain.full_applications():
            original_id = application.original_doc
            application.description = request.POST["%s_description" % original_id]
            if application.description != '':
                application.save()

        if new_domain is None:
            return render_to_response(request, 'domain/snapshot_settings.html',
                    {'domain': domain.name,
                     'form': form,
                     'latest_applications': latest_applications,
                     'error_message': 'Snapshot creation failed; please try again'})

        messages.success(request, "Created snapshot. The snapshot will be posted to the project store pending approval by admins.")
        return redirect('domain_snapshot_settings', domain.name)

@domain_admin_required
def set_published_snapshot(request, domain, snapshot_name=''):
    domain = request.project
    snapshots = domain.snapshots()
    if request.method == 'POST':
        for snapshot in snapshots:
            if snapshot.published:
                snapshot.published = False
                snapshot.save()
        if snapshot_name != '':
            published_snapshot = Domain.get_by_name(snapshot_name)
            if published_snapshot.original_doc != domain.name:
                messages.error(request, "Invalid snapshot")
            published_snapshot.published = True
            published_snapshot.save()
    return redirect('domain_copy_snapshot', domain.name)

@require_previewer
@login_and_domain_required
def snapshot_info(request, domain):
    domain = Domain.get_by_name(domain)
    user_sees_meta = request.couch_user.is_previewer()
    if user_sees_meta:
        form = DomainMetadataForm(initial={
            'default_timezone': domain.default_timezone,
            'case_sharing': json.dumps(domain.case_sharing),
            'city': domain.city,
            'country': domain.country,
            'region': domain.region,
            'project_type': domain.project_type,
            'customer_type': domain.customer_type,
            'is_test': json.dumps(domain.is_test),
            'description': domain.description,
            'is_shared': domain.is_shared,
            'license': domain.license
        })
    else:
        form = DomainGlobalSettingsForm(initial={
            'default_timezone': domain.default_timezone,
            'case_sharing': json.dumps(domain.case_sharing),

            })
    fields = []
    for field in form.visible_fields():
        value = field.value()
        if value:
            if value == 'false':
                value = False
            if value == 'true':
                value = True
            if isinstance(value, bool):
                value = 'Yes' if value else 'No'
            fields.append({'label': field.label, 'value': value})
    return render_to_response(request, 'domain/snapshot_info.html', {'domain': domain.name,
                                                                     'fields': fields,
                                                                     "languages": request.project.readable_languages(),
                                                                     "applications": request.project.applications()})

@require_previewer
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
                m_file.license[domain] = request.POST.get('%s_license' % m_file._id, 'public')
            m_file.save()
        messages.success(request, "Multimedia updated successfully!")

    return render_to_response(request, 'domain/admin/media_manager.html', {'domain': domain,
        'media': [{
            'license': m.license.get(domain, 'public'),
            'shared': domain in m.shared_by,
            'url': m.url(),
            'm_id': m._id,
            'tags': m.tags.get(domain, []),
            'type': m.doc_type
                   } for m in media],
        'licenses': LICENSES.items()
                                                                     })
