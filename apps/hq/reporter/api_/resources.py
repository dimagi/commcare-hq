from datetime import datetime, timedelta
from django.core import serializers
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.template import RequestContext
from django_rest_interface.resource import Resource
from transformers.xml import xmlify
from transformers.http import responsify
from xformmanager.models import FormDefModel, Metadata
from hq.models import ReporterProfile
from hq.reporter.api_.reports import Report, DataSet, get_params, get_stats
from hq.reporter.metadata import get_user_id_count, get_username_count
import hq.utils as utils 

# TODO - pull out authentication stuff into some generic wrapper
# if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
#    return HttpResponseBadRequest("You do not have permissions to use this API.")

# <HACK>temporary hack for august 6 - TODO: remove
from hq.models import Domain

def daily_report(request):
    formdefs = FormDefModel.objects.filter(target_namespace__icontains='resolution_0.0.2a')
    if not formdefs:
        return HttpResponseBadRequest("No schema matches 'resolution_0.0.2a'")
    response = read(request=request, ids=[ f.pk for f in formdefs ], \
                                     index='Day', value=['Referrals'])
    return response

def user_report(request):
    formdefs = FormDefModel.objects.filter(target_namespace__icontains='resolution_0.0.2a')
    if not formdefs:
        return HttpResponseBadRequest("No schema matches 'resolution_0.0.2a'")
    response = read(request=request, ids=[ formdefs[0].pk ], \
                                    index='User', value=['Referrals'])
    return response
# </HACK>

# it doesn't really make sense to define any of this as a 'resource'
# since reports are by definition read-only
def read(request, ids=[], index='',value=[]):
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
    stats = None
    if request.REQUEST.has_key('stats'):
        stats = [v.strip() for v in request.GET['stats'].split(',')]
    report = get_report(request, ids, index, value, start_date, end_date, stats)
    xml = xmlify(report)
    response = responsify('xml', xml)
    return response


def get_report(request, ids, index, value, start_date, end_date, stats):
    """ There's probably a more generic way of hanlding this, 
    but we do need to support fairly custom titles and names for
    some of these elements. Anyways, it's worth revisiting and
    refactoring this later
    
    """
    if index.lower() == 'user':
        return get_user_activity_report(request, ids, index, value, start_date, end_date, stats)
    elif index.lower() == 'day':
        return get_daily_activity_report(request, ids, index, value, start_date, end_date, stats)
    raise Exception("Your request does not match any known reports.")

# TODO - filter returned data by user's domain
def get_user_activity_report(request, ids, index, value, start_date, end_date, stats):
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

    
    # CHW Group Total Activity Report
    report = Report("CHW Group Total Activity Report")
    report.generating_url = request.get_full_path()
    total_metadata = Metadata.objects.filter(submission__submission__submit_time__gte=start_date)
    total_metadata = total_metadata.filter(submission__submission__submit_time__lte=end_date)
    metadata = total_metadata.filter(formdefmodel__in=ids).order_by('id')
    if not metadata:
        raise Exception("Metadata of schema with id in %s not found." % str(ids) )
    
    # when 'organization' is properly populated, we can start using that
    #       member_list = utils.get_members(organization)
    # for now, just use domain
    member_list = [r.chw_username for r in ReporterProfile.objects.filter(domain=domain)]
    # get the specified forms
    for id in ids:
        dataset = DataSet( unicode(value[0]) + " per " + unicode(index) )
        dataset.entries.value = unicode(value[0])
        dataset.entries.index_ = unicode(index)
        form_metadata = metadata.filter(formdefmodel=id)
        #for param in params:
        #    dataset.params[param.name] = param.value
        # e.g. stat='sum'
        #for stat in stats:
        #    dataset.stats[stat.name] = exec_stat(stat,form_metadata)
        for member in member_list:
            # entries are tuples of dates and counts
            dataset.entries.append( (member, form_metadata.filter(username=member).count()) )
        report.datasets.append(dataset)
    # get a sum of all forms
    dataset = DataSet( "Visits per " + unicode(index) )
    dataset.entries.value = "Visits"
    dataset.entries.index_ = unicode(index)
    for member in member_list:
        dataset.entries.append( (member, total_metadata.filter(username=member).count()) )
    report.datasets.append(dataset)
    return report

# TODO - filter returned data by user's domain
def get_daily_activity_report(request, ids, index, value, start_date, end_date, stats):
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

    if request.GET.has_key('chw'): chw = request.GET['chw']
    else: raise Exception("This reports requires a CHW parameter")

    # TODO - this currrently only tested for value lists of size 1. test. 
    # CHW Daily Activity Report
    report = Report("CHW Daily Activity Report")
    report.generating_url = request.get_full_path()
    # when 'organization' is properly populated, we can start using that
    #       member_list = utils.get_members(organization)
    # for now, just use domain
    
    member_list = [r.chw_username for r in ReporterProfile.objects.filter(domain=domain)]
    form_list = FormDefModel.objects.filter(pk__in=ids)
    username_counts = get_username_count(form_list, member_list, start_date, end_date)
    # return2 dict of username to: [firstdaycount, seconddaycount, thirddaycount]
    
    for form in form_list:
        dataset = DataSet( unicode(value[0]) + " per " + unicode(index) )
        dataset.entries.value = unicode(value[0])
        dataset.entries.index_ = unicode(index)
        
        dataset.params = get_params(request)
        date = start_date
        day = timedelta(days=1)
        if chw not in username_counts:
            raise Exception("Username could not be matched to any submitted forms")
        for daily_count in username_counts[chw]:
            # entries are tuples of dates and daily counts
            dataset.entries.append( (date.strftime("%Y-%m-%d"),daily_count) )
            date = date + day
        dataset.stats = get_stats(stats, dataset.entries)
        report.datasets.append(dataset)
    # get a sum of all the forms
    dataset = DataSet( "Visits per " + unicode(index) )
    dataset.entries.value = "Visits"
    dataset.entries.index_ = unicode(index)
    dataset.params = get_params(request)
    member_list = [r.chw_username for r in ReporterProfile.objects.filter(domain=domain)]
    username_counts = get_username_count(None, member_list, start_date, end_date)
    date = start_date
    day = timedelta(days=1)
    if chw not in username_counts:
        raise Exception("Username could not be matched to any submitted forms")
    for daily_count in username_counts[chw]:
        # entries are tuples of dates and daily counts
        dataset.entries.append( (date.strftime("%Y-%m-%d"),daily_count) )
        date = date + day
    dataset.stats = get_stats(stats, dataset.entries)
    report.datasets.append(dataset)      
    return report

