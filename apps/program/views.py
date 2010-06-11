from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404

from webutils import render_to_response

from hqutils import get_post_redirect
from domain.decorators import login_and_domain_required, domain_admin_required
from program.models import Program, ProgramMembership
from program.forms import ProgramForm

@login_and_domain_required
@domain_admin_required
def list_programs(request):
    """List the programs for a particular domain"""
    programs = Program.objects.filter(domain=request.user.selected_domain)
    return render_to_response(request, "program/program_list.html",
                              {"programs": programs})

@login_and_domain_required
@domain_admin_required
def add_program(request):
    """Add a program to a domain"""
    if request.method == "POST":
        form = ProgramForm(request.POST)
        if form.is_valid():
            new_program = form.save(commit=False)
            new_program.domain = request.user.selected_domain
            new_program.save()
            if "users" in request.POST:
                user_ids = request.POST.getlist("users")
            else:
                user_ids = set([])
            for user_id in user_ids:
                new_program.add_user(User.objects.get(id=user_id))
            return HttpResponseRedirect(reverse('list_programs'))
    else:
        form = ProgramForm()
    
    users = User.objects.filter(domain_membership__domain = request.user.selected_domain)
    return render_to_response(request, "program/program_add.html",
                              {"form": form, "users": users})
    
@login_and_domain_required
@domain_admin_required
def edit_program(request, program_id):
    program = get_object_or_404(Program.objects.filter(domain=request.user.selected_domain), pk=program_id)
    if request.method == "POST":
        original_ids = set([user.id for user in program.get_users()])
        form = ProgramForm(request.POST, instance=program)
        if form.is_valid():
            edit_program = form.save(commit=False)
            edit_program.domain = request.user.selected_domain
            edit_program.save()
            
            if "users" in request.POST:
                updated_ids = set([int(id) for id in request.POST.getlist("users")])
            else:
                updated_ids = set([])
            to_remove = original_ids.difference(updated_ids)
            to_add = updated_ids.difference(original_ids)
            for user_id in to_add:
                edit_program.add_user(User.objects.get(id=user_id))
            for user_id in to_remove:
                edit_program.remove_user(User.objects.get(id=user_id))
                
            return HttpResponseRedirect(reverse('list_programs'))
    else:
        form = ProgramForm(instance=program)
        
    users = User.objects.filter(domain_membership__domain = request.user.selected_domain)
    def add_selected(user, program):
        if user in program.get_users():    user.selected = True
        return user
    users = map(add_selected, users, (program,) * users.count())
    return render_to_response(request, "program/program_add.html",
                              {"form": form, "users": users})
    
    
@login_and_domain_required
@domain_admin_required
def delete_program(request, program_id):
    """Delete a program.  Does not warn you."""
    # Note that this currently breaks standard http don't-modify-on-GET expectations.
    # TODO: use a POST
    program = get_object_or_404(Program.objects.filter(domain=request.user.selected_domain), pk=program_id)
    program.delete()
    return HttpResponseRedirect(reverse('list_programs'))
    
