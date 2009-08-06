from datetime import datetime, timedelta
from django.core import serializers
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.template import RequestContext
from django_rest_interface.resource import Resource
from transformers.xml import *
from transformers.http import *
from xformmanager.models import FormDefModel, Metadata
from hq.models import ReporterProfile
from hq.reporter.api_.reports import *
from hq.reporter.metadata import get_user_id_count, get_username_count
import hq.utils as utils 

# temporary hack - TODO: remove
from hq.models import Domain

# TODO - pull out authentication stuff into some generic wrapper
# if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
#    return HttpResponse("You do not have permissions to use this API.")


def daily_report(request):
    formdefs = FormDefModel.objects.filter(target_namespace__icontains='resolution')
    if not formdefs:
        return HttpResponseBadRequest("No schema matches 'resolution'")
    response = read(request=request, ids=[ formdefs[0].pk ], \
                                     index='day', value=['count'])
    return response

def user_report(request):
    formdefs = FormDefModel.objects.filter(target_namespace__icontains='resolution')
    if not formdefs:
        return HttpResponseBadRequest("No schema matches 'resolution'")
    response = read(request=request, ids=[ formdefs[0].pk ], \
                                    index='user', value=['count'])
    return response
    
# it doesn't really make sense to define any of this as a 'resource'
# since reports are by definition read-only
def read(request, ids=[], index='',value=[]):
    # temporary hack to get pf api working. TODO - remove
    try:
        domain = Domain.objects.get(name='Pathfinder')
    except Domain.DoesNotExist:
        return HttpResponseBadRequest( \
            "Domain 'Pathfinder' does not exist.")
    
    #try:
    #    extuser = ExtUser.objects.get(id=request.user.id)
    #except ExtUser.DoesNotExist:
    #    return HttpResponseBadRequest( \
    #        "You do not have permission to use this API.")
    #domain = extuser.domain
    
    if not ids:
        if request.REQUEST.has_key('ids'):
            ids = [v.strip() for v in request.GET['id'].split(',')]
    if not index:
        if request.REQUEST.has_key('index'):
            index = request.GET['index']
        else:
            return HttpResponseBadRequest("Must specify index (x-axis)")    
    if not value:
        if request.REQUEST.has_key('value'):
            values = [v.strip() for v in request.GET['value'].split(',')]
        else:
            return HttpResponseBadRequest("Must specify value (y-axes)")
    start_date = None
    if request.REQUEST.has_key('start-date'):
        start_date = datetime.strptime(request.GET['start-date'],"%Y-%m-%d")
    if start_date is None:
        return HttpResponseBadRequest("Must specify start_date")   
    end_date = None
    if request.REQUEST.has_key('end-date'):
        end_date = datetime.strptime(request.GET['end-date'],"%Y-%m-%d")
    if end_date is None:
        return HttpResponseBadRequest("Must specify end_date")   
    if request.REQUEST.has_key('stat'):
        stat = [v.strip() for v in request.GET['stat'].split(',')]
    report = get_report(domain, ids, index, value, \
                    start_date, end_date,request.GET)
    xml = xmlify(report)
    response = responsify('xml', xml)
    return response


def get_report(domain, ids, index, value, start_date, end_date, params):
    """ There's probably a more generic way of hanlding this, 
    but we do need to support fairly custom titles and names for
    some of these elements. Anyways, it's worth revisiting and
    refactoring this later
    
    """
    if index == 'user':
        return get_user_activity_report(domain, ids, index, value, start_date, end_date, params)
    elif index == 'day':
        return get_daily_activity_report(domain, ids, index, value, start_date, end_date, params)
    raise Exception("Your request does not match any known reports.")

# TODO - filter returned data by user's domain
def get_user_activity_report(domain, ids, index, value, start_date, end_date, params):
    # CHW Group Total Activity Report
    report = Report("CHW Group Total Activity Report")
    metadata = Metadata.objects.filter(formdefmodel__in=ids).order_by('id')
    if not metadata:
        raise Exception("Metadata of schema with id in %s not found." % str(ids) )
    metadata = metadata.filter(submission__submission__submit_time__gte=start_date)
    metadata = metadata.filter(submission__submission__submit_time__lte=end_date)
    
    # when 'organization' is properly populated, we can start using that
    #       member_list = utils.get_members(organization)
    # for now, just use domain
    member_list = [r.chw_id for r in ReporterProfile.objects.filter(domain=domain)]
    # get the specified forms
    for id in ids:
        dataset = DataSet( str(value) + " for " + str(index) )
        form_metadata = metadata.filter(formdefmodel=id)
        #for param in params:
        #    dataset.params[param.name] = param.value
        # e.g. stat='sum'
        #for stat in stats:
        #    dataset.stats[stat.name] = exec_stat(stat,form_metadata)
        for member in member_list:
            # entries are tuples of dates and counts
            dataset.entries.append( (member, form_metadata.filter(chw_id=member).count()) )
        report.datasets.append(dataset)
    # get a sum of all forms
    return report

# TODO - filter returned data by user's domain
def get_daily_activity_report(domain, ids, index, value, start_date, end_date, params):
    # TODO - this currrently only works for value lists of size 1. FIX. 
    # CHW Daily Activity Report
    report = Report("CHW Daily Activity Report")
    form_list = FormDefModel.objects.filter(pk__in=ids)
    # when 'organization' is properly populated, we can start using that
    #       member_list = utils.get_members(organization)
    # for now, just use domain
    
    reporters = ReporterProfile.objects.filter(domain=domain)
    member_list = []
    for reporter in reporters:
        chw_username = reporter.chw_username
        member_list.append( chw_username )
    #member_list = [r.chw.id for r in ReporterProfile.objects.filter(domain=domain)]
    username_counts = get_username_count(form_list, member_list, start_date, end_date)
    # return2 dict of username to: [firstdaycount, seconddaycount, thirddaycount]
    
    if params.has_key('chw'): chw = params['chw']
    else: raise Exception("This reports requires a CHW parameter")
    for form in form_list:
        dataset = DataSet( unicode(value[0]) + " for " + unicode(index) )
        #for param in params:
        #    dataset.params[param.name] = param.value
        # e.g. stat='sum'
        #for stat in stats:
        #    dataset.stats[stat.name] = exec_stat(stat,form_metadata)
        date = start_date
        day = timedelta(days=1)
        if chw not in username_counts:
            raise Exception("Username could not be matched to any submitted forms")
        for daily_count in username_counts[chw]:
            # entries are tuples of dates and daily counts
            dataset.entries.append( (date.strftime("%Y-%m-%d"),daily_count) )
            date = date + day
        report.datasets.append(dataset)
    # get a sum of all forms
    return report
