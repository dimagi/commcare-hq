import datetime
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from corehq.apps.hqwebapp.views import logout
from corehq.apps.registration.forms import NewWebUserRegistrationForm
from corehq.apps.registration.utils import activate_new_user
from corehq.apps.users.models import Invitation, CouchUser
from dimagi.utils.web import render_to_response

from django.core.paginator import Paginator, InvalidPage, EmptyPage

# from hq.models import *
# from graphing.models import *




#get members under this supervisor for this group
def get_members_for_supervisor(organization, supervisor_user):
    pass

def get_supervisor_roles(user):
    """return an array of organizations that a user is a supervisor.  The array is empty if they are nothing"""
    raise Exception("Someone needs to fix this method to no longer be dependent on model relationship if they're going to use it!")
    
def get_membership(user):
    """return an array of organizations that a user belongs to.  The array is empty if they are nothing"""
    raise Exception("Someone needs to fix this method to no longer be dependent on model relationship if they're going to use it!")

def get_members(organization):
    """return an array of members in an organization"""
    raise Exception("Someone needs to fix this method to no longer be dependent on model relationship if they're going to use it!")

def get_chart_group(user):
    # todo this makes a mean assumption there's only one
    # group 
    try:
        prefs = GraphPref.objects.get(user=user)
        return  prefs.root_graphs.all()[0]
    except GraphPref.DoesNotExist:
        return None


def get_members_and_supervisors(organization):
    """Return a tuple (members[], supervisors[]) for a given organization.
       Deals with the empty lists and null objects for you so you don't have 
       to.
       The contents of the tuples are reporter objects.
       """
    members = []
    supervisors = []
    if organization:
        if organization.members:
            members = organization.members.reporters.all()
        if organization.supervisors:
            supervisors = organization.supervisors.reporters.all()  
    return (members, supervisors)
            
    
def get_date_range(startdate, enddate):
    """
    Returns a list of dates, including every day between startdate and enddate
    """
    if enddate < startdate:
        raise Exception("Passed in enddate that was before start date, did you flip your variables around?")
    
    if isinstance(startdate, datetime.datetime):  startdate = startdate.date()
    if isinstance(enddate, datetime.datetime):    enddate = enddate.date()
        
    totalspan = enddate-startdate
    return [startdate + timedelta(days=day) for day in range(0, totalspan.days+1)]
        
    
    
def get_dates(request, default_days=0):
    default_delta = timedelta(days=default_days)
    enddate = datetime.datetime.now().date()
    startdate = enddate - default_delta
    if request:
        for item in request.GET.items():
            if item[0] == 'startdate':
                startdate_str=item[1]
                startdate = datetime.datetime.strptime(startdate_str,'%m/%d/%Y').date()
            if item[0] == 'enddate':
                enddate_str=item[1]
                enddate = datetime.datetime.strptime(enddate_str,'%m/%d/%Y').date()
    return (startdate, enddate)

def get_dates_reports(request, default_days_active=0, default_days_late=0):
    default_delta_active = timedelta(days=default_days_active)
    default_delta_late = timedelta(days=default_days_late)
    enddate = datetime.datetime.now().date()
    startdate_active = enddate - default_delta_active
    startdate_late = enddate - default_delta_late
    if request:
        for item in request.GET.items():
            try:
                if item[0] == 'startdate_active':
                    startdate_active_str=item[1]
                    if startdate_active_str != '':
                        startdate_active = datetime.datetime.strptime(
                            startdate_active_str,'%m/%d/%Y').date()
                if item[0] == 'startdate_late':
                    startdate_late_str=item[1]
                    if startdate_late_str != '':
                        startdate_late = datetime.datetime.strptime(
                            startdate_late_str,'%m/%d/%Y').date()
                if item[0] == 'enddate':
                    enddate_str=item[1]
                    if enddate_str != '':
                        enddate = datetime.datetime.strptime(enddate_str,
                                                         '%m/%d/%Y').date()
            except ValueError:
                print 'Invalid date string' #TODO: This isn't right
    return (startdate_active, startdate_late, enddate)

def get_table_display_properties(request, default_items=25, default_sort_column = "id", 
                                 default_sort_descending = True, default_filters = {}):
    """Extract some display properties from a request object.  The following 
       parameters (with default values) are extracted.  Andy of the defaults
       can be overridden by passing in values.
       items: 25 (the number of items to paginate at a time)
       sort_column: id (the column to sort by)
       sort_descending: True (the sort order of the column)
       filters: {} (key, value pairs of filters to apply)
    """
    items = default_items
    sort_column = default_sort_column
    sort_descending = default_sort_descending
    # odd, for some reason pass-by-reference can confuse the default types here
    filters = default_filters.copy()
    # if no request found, just resort to all the defaults, but 
    # don't fail hard.
    if request:
        # extract from request
        if "items" in request.GET:
            try:
                items = int(request.GET["items"])
            except Exception:
                # just default to the above if we couldn't 
                # parse it
                pass
        if "sort_column" in request.GET:
            sort_column = request.GET["sort_column"]
        if "sort_descending" in request.GET:
            # a very dumb boolean parser
            sort_descending_str = request.GET["sort_descending"]
            if sort_descending_str.startswith("f"):
                sort_descending = False
            else:
                sort_descending = True
        found_filters = {}
        for param in request.GET:
            if param.startswith('filter_'):
                # we convert 'filter_x' into 'x' (the name of the field)
                field = param.split('_',1)[-1]
                found_filters[str(field)] = request.GET[param]
        if found_filters:
            filters = found_filters
    return (items, sort_column, sort_descending, filters)
    
def get_query_set(model_class, sort_column="id", sort_descending=True, filters={}):
    """Gets a query set, based on the results of the get_table_display_properties
       method, and a model.""" 
    sort_modifier = ""
    if sort_descending:
        sort_modifier = "-"
    return model_class.objects.filter(**filters).order_by("%s%s"% (sort_modifier, sort_column))
    
def paginate(request, data, rows_per_page=25):
    '''Helper call to provide django pagination of data'''
    paginator = Paginator(data, rows_per_page) 
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    try:
        data_pages = paginator.page(page)
    except (EmptyPage, InvalidPage):
        data_pages = paginator.page(paginator.num_pages)
    return data_pages

def build_url(relative_path, request=None):
    '''Attempt to build a fully qualified url.  It will first try to back
       it out of the request object, if specified.  Failing that it will 
       look for a django setting: SERVER_ROOT_URL.  Failing that, it defaults
       to localhost:8000.
    '''
    if request:
        return request.build_absolute_uri(relative_path)
    elif hasattr(settings, "SERVER_ROOT_URL"):
        return "%s%s" % (settings.SERVER_ROOT_URL, relative_path)
    else:
        return "http://localhost:8000%s" % relative_path
        
        
def get_post_redirect(request, get_callback, post_callback,
                      get_template_name = None, post_template_name = None):
    """
    Given a django request and callback methods for get and post, redirect
    to one of those methods based on the operation of the request.
    
    Assumes that the callback methods take in a single required object (the 
    request) and (optionally) a template name.
    
    You can pass templates to the get and post callback methods, but if none 
    are specified then none will be called.
    """
    if request.method == "GET":  
        if get_template_name:  return get_callback(request, get_template_name)
        else:                  return get_callback(request)
    elif request.method == "POST": 
        if post_template_name: return post_callback(request, post_template_name)        
        else:                  return post_callback(request)
    raise Exception("Request method could not be matched.  Expected a GET or a POST.")

def check_for_redirect(request):
    if request.GET.get('switch') == 'true':
        logout(request)
        return redirect_to_login(request.path)
    if request.GET.get('create') == 'true':
        logout(request)
        return HttpResponseRedirect(request.path)
    return False

def check_for_accepted(request, invitation):
    if invitation.is_accepted:
        messages.error(request, "Sorry, that invitation has already been used up. "
                                "If you feel this is a mistake please ask the inviter for "
                                "another invitation.")
        return HttpResponseRedirect(reverse("login"))
    return False

class InvitationView():
    inv_type = Invitation
    template = ""
    need = [] # a list of strings containing which parameters of the call function should be set as attributes to self

    def added_context(self):
        return {}

    def validate_invitation(self, invitation):
        pass

    @property
    def success_msg(self):
        return "You have been successfully invited"

    @property
    def redirect_to_on_success(self):
        raise NotImplementedError

    def invite(self, invitation, user):
        raise NotImplementedError

    def _invite(self, invitation, user):
        self.invite(invitation, user)
        invitation.is_accepted = True
        invitation.save()
        messages.success(self.request, self.success_msg)

    def __call__(self, request, invitation_id, **kwargs):
        # add the correct parameters to this instance
        self.request = request
        for k, v in kwargs.iteritems():
            if k in self.need:
                setattr(self, k, v)

        if request.GET.get('switch') == 'true':
            logout(request)
            return redirect_to_login(request.path)
        if request.GET.get('create') == 'true':
            logout(request)
            return HttpResponseRedirect(request.path)

        invitation = self.inv_type.get(invitation_id)

        if invitation.is_accepted:
            messages.error(request, "Sorry, that invitation has already been used up. "
                                    "If you feel this is a mistake please ask the inviter for "
                                    "another invitation.")
            return HttpResponseRedirect(reverse("login"))

        self.validate_invitation(invitation)

        if request.user.is_authenticated():
            if request.couch_user.username != invitation.email:
                messages.error(request, "The invited user %s and your user %s do not match!" % (invitation.email, request.couch_user.username))

            if request.method == "POST":
                couch_user = CouchUser.from_django_user(request.user)
                self._invite(invitation, couch_user)
                return HttpResponseRedirect(self.redirect_to_on_success)
            else:
                mobile_user = CouchUser.from_django_user(request.user).is_commcare_user()
                context = self.added_context()
                context.update({
                    'mobile_user': mobile_user,
                    "invited_user": invitation.email if request.couch_user.username != invitation.email else "",
                })
                return render_to_response(request, self.template, context)
        else:
            if request.method == "POST":
                form = NewWebUserRegistrationForm(request.POST)
                if form.is_valid():
                    # create the new user
                    user = activate_new_user(form)
                    user.save()
                    messages.success(request, "User account for %s created! You may now login." % form.cleaned_data["email"])
                    self._invite(invitation, user)
                    return HttpResponseRedirect(reverse("login"))
            else:
                form = NewWebUserRegistrationForm(initial={'email': invitation.email})

        return render_to_response(request, self.template, {"form": form})

