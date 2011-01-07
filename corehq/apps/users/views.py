from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.views.decorators.http import require_POST
from corehq.apps.sms.views import get_sms_autocomplete_context
from corehq.util.webutils import render_to_response
from corehq.apps.domain.models import Domain
from corehq.apps.users.forms import UserForm, CommCareAccountForm
from corehq.apps.users.models import CouchUser, create_hq_user_from_commcare_registration_info
from django.contrib.admin.views.decorators import staff_member_required
from django_digest.decorators import httpdigest
from corehq.apps.groups.models import Group
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.users.util import couch_user_from_django_user



def _users_context(request, domain):
    return {
         'web_users': CouchUser.view("users/web_users_by_domain", key=domain),
         'domain': domain
    }
@login_and_domain_required
def users(req, domain, template="users/users_base.html"):
    return HttpResponseRedirect(reverse(
        "corehq.apps.users.views.my_account",
        args=[domain],
    ))
@login_and_domain_required
def web_users(request, domain, template="users/web_users.html"):
    context = _users_context(request, domain)
    return render_to_response(request, template, context)

@login_and_domain_required
def commcare_users(request, domain, template="users/commcare_users.html"):
    context = _users_context(request, domain)
    context.update({
        'all_users': CouchUser.view("users/commcare_users_by_domain", key=domain),
    })
    return render_to_response(request, template, context)

@login_and_domain_required
def my_account(request, domain, template="users/account.html"):
    return edit(request, domain, request.couch_user.couch_id, template)

@login_and_domain_required
def account(request, domain, couch_id, template="users/account.html"):
    return edit(request, domain, couch_id, template)

@login_and_domain_required
def my_phone_numbers(request, domain, template="users/phone_numbers.html"):
    return phone_numbers(request, domain, request.couch_user.couch_id, template)

@login_and_domain_required
def phone_numbers(request, domain, couch_id, template="users/phone_numbers.html"):
    context = {}
    couch_user = CouchUser.get(couch_id)
    if request.method == "POST" and 'phone_number' in request.POST:
        phone_number = request.POST['phone_number']
        couch_user.add_phone_number(phone_number)
        couch_user.save()
        context['status'] = 'phone number added'
    context['phone_numbers'] = couch_user.phone_numbers
    context.update({"domain": domain, "couch_user":couch_user })
    return render_to_response(request, template, context)

@require_POST
@login_and_domain_required
def delete_phone_number(request, domain, user_id, phone_number):
    user = CouchUser.get(user_id)
    for i in range(0,len(user.phone_numbers)):
        if user.phone_numbers[i].number == phone_number:
            del user.phone_numbers[i]
            break
    user.save()
    return HttpResponseRedirect(reverse("phone_numbers", args=(domain, user_id )))

@login_and_domain_required
def my_commcare_accounts(request, domain, template="users/commcare_accounts.html"):
    return commcare_accounts(request, domain, request.couch_user.couch_id, template)

@login_and_domain_required
def commcare_accounts(request, domain, couch_id, template="users/commcare_accounts.html"):
    context = {}
    couch_user = CouchUser.get(couch_id)
    my_commcare_usernames = [c.django_user.username for c in couch_user.commcare_accounts]
    other_commcare_users = []
    all_commcare_users = CouchUser.view("users/commcare_users_by_domain", key=domain).all()
    for u in all_commcare_users:
        # we don't bother showing the duplicate commcare users. 
        # these need to be resolved elsewhere.
        if hasattr(u,'is_duplicate') and u.is_duplicate == True:
            continue
        if u.django_user.username not in my_commcare_usernames:
            other_couch_user = CouchUser.get(u.get_id)
            if hasattr(other_couch_user, 'django_user'):
                u.couch_user_id = other_couch_user.get_id
                u.couch_user_username = other_couch_user.django_user.username
            other_commcare_users.append(u)
    context.update({"domain": domain, 
                    "couch_user":couch_user, 
                    "commcare_users":couch_user.commcare_accounts, 
                    "other_commcare_users":other_commcare_users, 
                    })
    return render_to_response(request, template, context)

@require_POST
@login_and_domain_required
def link_commcare_account_to_user(request, domain, couch_user_id, commcare_username):
    user = CouchUser.get(couch_user_id)
    if 'commcare_couch_user_id' not in request.POST: 
        return Http404("Poorly formed link request")
    user.link_commcare_account(domain, 
                               request.POST['commcare_couch_user_id'], 
                               commcare_username)
    return HttpResponseRedirect(reverse("commcare_accounts", args=(domain, couch_user_id)))

@require_POST
@login_and_domain_required
def unlink_commcare_account(request, domain, couch_user_id, commcare_user_index):
    user = CouchUser.get(couch_user_id)
    if commcare_user_index:
        user.unlink_commcare_account(domain, commcare_user_index)
        user.save()
    return HttpResponseRedirect(reverse("commcare_accounts", args=(domain, couch_user_id )))

@login_and_domain_required
def my_domains(request, domain, template="users/domain_accounts.html"):
    return domain_accounts(request, domain, request.couch_user.couch_id, template)

@login_and_domain_required
def domain_accounts(request, domain, couch_id, template="users/domain_accounts.html"):
    context = {}
    couch_user = CouchUser.get(couch_id)
    if request.method == "POST" and 'domain' in request.POST:
        domain = request.POST['domain']
        couch_user.add_domain_membership(domain)
        couch_user.save()
        context['status'] = 'domain added'
    my_domains = [dm.domain for dm in couch_user.domain_memberships]
    context['other_domains'] = [d.name for d in Domain.objects.exclude(name__in=my_domains)]
    context.update({"user": request.user, 
                    "domain": domain,
                    "domains": [dm.domain for dm in couch_user.domain_memberships], 
                    "couch_user":couch_user })
    return render_to_response(request, template, context)

@require_POST
@login_and_domain_required
def add_domain_membership(request, domain, user_id, domain_name):
    user = CouchUser.get(user_id)
    if domain_name:
        user.add_domain_membership(domain_name)
        user.save()
    return HttpResponseRedirect(reverse("domain_accounts", args=(domain, user_id)))

@require_POST
@login_and_domain_required
def delete_domain_membership(request, domain, user_id, domain_name):
    user = CouchUser.get(user_id)
    for i in range(0,len(user.domain_memberships)):
        if user.domain_memberships[i].domain == domain_name:
            del user.domain_memberships[i]
            break
    user.save()
    return HttpResponseRedirect(reverse("domain_accounts", args=(domain, user_id )))

@login_and_domain_required
def edit(request, domain, couch_id=None, template="users/account.html"):
    """
    Edit a user
    """
    context = _users_context(request, domain)
    if couch_id is None:
        django_user = User()
    else:
        user = CouchUser.get(couch_id)
        django_user = user.default_django_user
    if request.method == "POST":
        form = UserForm(request.POST)
        if form.is_valid():
            django_user.username = form.cleaned_data['username']
            django_user.first_name = form.cleaned_data['first_name']
            django_user.last_name = form.cleaned_data['last_name']
            django_user.email = form.cleaned_data['email']
            django_user.save()
            context['status'] = 'changes saved'
    else:
        form = UserForm()
        form.initial['username'] = django_user.username
        form.initial['first_name'] = django_user.first_name
        form.initial['last_name'] = django_user.last_name
        form.initial['email'] = django_user.email
    couch_user = couch_user_from_django_user(django_user)
    context.update({"form": form, "domain": domain, "couch_user": couch_user })
    return render_to_response(request, template, context)

@httpdigest
@login_and_domain_required
def httpdigest(request, domain):
    return HttpResponse("ok")

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
GROUP VIEWS
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

@login_and_domain_required
def all_groups(request, domain, template="groups/all_groups.html"):
    all_groups = Group.view("groups/by_domain", key=domain)
    return render_to_response(request, template, {
        'domain': domain,
        'all_groups': all_groups
    })

@login_and_domain_required
def group_members(request, domain, group_name, template="groups/group_members.html"):
    context = {}
    group = Group.view("groups/by_name", key=group_name).one()
    if group is None:
        raise Http404("Group %s does not exist" % group_name)
    members = CouchUser.view("users/by_group", key=[domain, group.name], include_docs=True).all()
    member_ids = [member._id for member in members]
    #members = [m['doc'] for m in result]
    #members = [m for m in CouchUser.view("users/all_users", keys=member_ids).all()]
    member_commcare_users = []
    for member in members:
        for commcare_account in member.commcare_accounts:
            commcare_account.couch_user_id = member.get_id
            member_commcare_users.append(commcare_account)
    # note: we believe couch/hq users and commcare users unilaterally share group membership
    # i.e. there's no such thing as commcare_account group membership, only couch_user group membership
    nonmember_commcare_users = []
    all_users = CouchUser.view("users/by_domain", key=domain).all()
    for user in all_users:
        if user.get_id not in member_ids:
            commcare_accounts = []
            for commcare_account in user.commcare_accounts:
                commcare_account.couch_user_id = user.get_id
                commcare_accounts.append(commcare_account)
            nonmember_commcare_users.extend(commcare_accounts)
    context.update({"domain": domain,
                    "group": group,
                    "members": member_commcare_users, 
                    "nonmembers": nonmember_commcare_users, 
                    })
    return render_to_response(request, template, context)

@login_and_domain_required
def my_groups(request, domain, template="groups/groups.html"):
    return group_membership(request, domain, request.couch_user._id, template)

@login_and_domain_required
def group_membership(request, domain, couch_user_id, template="groups/groups.html"):
    context = {}
    couch_user = CouchUser.get(couch_user_id)
    if request.method == "POST" and 'group' in request.POST:
        group = request.POST['group']
        group.add_user(couch_user)
        group.save()
        context['status'] = '%s joined group %s' % (couch_user._id, group.name)
    my_groups = Group.view("groups/by_user", key=couch_user_id).all()
    all_groups = Group.view("groups/by_domain", key=domain).all()
    other_groups = []
    for group in all_groups:
        if group.name not in [g.name for g in my_groups]:
            other_groups.append(group)
    #other_groups = [group for group in all_groups if group not in my_groups]
    context.update({"domain": domain,
                    "groups": my_groups, 
                    "other_groups": other_groups,
                    "couch_user":couch_user })
    return render_to_response(request, template, context)

@login_and_domain_required
def add_commcare_account(request, domain, template="users/add_commcare_account.html"):
    """
    Create a new commcare account
    """
    if request.method == "POST":
        form = CommCareAccountForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            couch_user = create_hq_user_from_commcare_registration_info(domain, username, password, 
                                                                        imei='Generated from HQ')
            # set commcare account UUID to match the couch id
            couch_user.commcare_accounts[0].UUID = couch_user.get_id
            couch_user.save()
            return HttpResponseRedirect(reverse("commcare_accounts", args=[domain, request.couch_user.get_id]))  
    else:
        form = CommCareAccountForm()
    return render_to_response(request, template, 
                              {"form": form,
                               "couch_user": request.couch_user,
                               "domain": domain })

@login_and_domain_required
def test_autocomplete(request, domain, template="users/test_autocomplete.html"):
    context = _users_context(request, domain)
    context.update(get_sms_autocomplete_context(request, domain))
    return render_to_response(request, template, context)