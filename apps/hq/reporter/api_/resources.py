import operator
from datetime import datetime, timedelta
from django.http import HttpResponseBadRequest
from transformers.xml import xmlify
from transformers.http import responsify
from xformmanager.models import FormDefModel, Metadata
from hq.models import ReporterProfile
from hq.reporter.api_.reports import Report, DataSet, Values
from hq.reporter.metadata import get_username_count, get_timespan
from domain.decorators import login_and_domain_required

# TODO - clean up index/value once we hash out this spec more properly
# TODO - pull out authentication stuff into some generic wrapper

def report(request, ids=[], index='', value=[]):
    """ Parses GET values, calls the appropriate report, formats it, and returns """
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
            value = [v.strip() for v in request.GET['value'].split(',')]
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
    try:
        _report = get_report(request, ids, index, value, start_date, end_date, stats)
    except Exception, e:
        return HttpResponseBadRequest(str(e))
    xml = xmlify(_report)
    response = responsify('xml', xml)
    return response

@login_and_domain_required
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

@login_and_domain_required
def get_user_activity_report(request, ids, index, value, start_date, end_date, stats):
    """ CHW Group Total Activity Report - submissions per user over time

    ids: list of form id's
    index: title for the x-axis. something like, 'users', 'chws', etc. 
    value: title for the y-axis. usually corresponds to the form name(s)
    start_date: start of reporting period
    end_date: end of reporting period
    stats: any requested stats. 
    Returns a Report object populated with requested data. 
    
    """    

    domain = request.user.selected_domain
    if not ids: raise Exception("The requested form was not found")
    
    _report = Report("CHW Group Total Activity Report")
    _report.generating_url = request.path
    metadata = Metadata.objects.filter(timestart__gte=start_date)
    # the query below is used if you want to query by submission time (instead of form completion time)
    #metadata = Metadata.objects.filter(attachment__submission__submit_time__gte=start_date)
    
    # since we are working at a granularity of 'days', we want to make sure include 
    # complete days in our queries, so we round up
    timespan = get_timespan(start_date, end_date)
    delta = timedelta(days=timespan.days+1)
    metadata = metadata.filter(timeend__lt=start_date+delta)
    # the query below is used if you want to query by submission time (instead of form completion time)
    #metadata = metadata.filter(attachment__submission__submit_time__lte=end_date)
    
    dataset = DataSet( unicode(value[0]) + " per " + unicode(index) )
    dataset.indices = unicode(index)
    dataset.params = request.GET

    # when 'organization' is properly populated, we can start using that
    #       member_list = utils.get_members(organization)
    # for now, just use domain
    member_list = [r.chw_username for r in ReporterProfile.objects.filter(domain=domain).order_by("chw_username")]

    # get a sum of all forms
    visits_per_member = Values( "visits" )
    for member in member_list:
        visits_per_member.append( (member, metadata.filter(username=member).count()) )
    visits_per_member.run_stats(stats)
    visits_per_member.sort(key=operator.itemgetter(1), reverse=True) 
    dataset.valuesets.append( visits_per_member )
    
    # this report only requires the first form. you can imagine other reports doing 
    # this iteration: for id in ids:
    form_per_member = Values( unicode(value[0]) )
    form_metadata = metadata.filter(formdefmodel=ids[0])
    for member in member_list:
        # values are tuples of dates and counts
        form_per_member.append( (member, form_metadata.filter(username=member).count()) )
    form_per_member.run_stats(stats)
    form_per_member.sort(key=operator.itemgetter(1), reverse=True) 
    dataset.valuesets.append( form_per_member )
    
    _report.datasets.append(dataset)
    return _report

@login_and_domain_required
def get_daily_activity_report(request, ids, index, value, start_date, end_date, stats):
    """ CHW Daily Activity Report - submissions per day by user

    ids: list of form id's. this report returns the sum of all ids listed. 
    index: title for the x-axis. something like, 'day', 'session', etc. 
    value: title for the y-axis. usually corresponds to the form name(s)
    start_date: start of reporting period
    end_date: end of reporting period
    stats: any requested stats. 
    Returns a Report object populated with requested data. 
    
    """
    
    domain = request.user.selected_domain
    
    if request.GET.has_key('chw'): chw = request.GET['chw']
    else: raise Exception("This reports requires a CHW parameter")

    if not ids: raise Exception("The requested form was not found")

    # TODO - this currrently only tested for value lists of size 1. test. 
    _report = Report("CHW Daily Activity Report")
    _report.generating_url = request.path
    # when 'organization' is properly populated, we can start using that
    #       member_list = utils.get_members(organization)
    # for now, just use domain    
    member_list = [r.chw_username for r in ReporterProfile.objects.filter(domain=domain)]
    if chw not in member_list: raise Exception("No matching CHW could be identified")
    
    dataset = DataSet( unicode(value[0]) + " per " + unicode(index) )
    dataset.indices = unicode(index)
    dataset.params = request.GET
    
    values = get_daily_activity_values('Visits', None, chw, member_list, start_date, end_date, stats, domain)
    dataset.valuesets.append( values )
    
    form_list = FormDefModel.objects.filter(pk__in=ids)
    values = get_daily_activity_values(unicode(value[0]), form_list, chw, member_list, start_date, end_date, stats, domain)
    dataset.valuesets.append( values )
    
    _report.datasets.append(dataset)      
    return _report

def get_daily_activity_values(name, form_list, chw, member_list, start_date, end_date, stats, domain):
    # get a sum of all the forms
    member_list = [r.chw_username for r in ReporterProfile.objects.filter(domain=domain)]
    if chw not in member_list: raise Exception("No matching CHW could be identified")
    username_counts = get_username_count(form_list, member_list, start_date, end_date)
    date = start_date
    day = timedelta(days=1)
    values_per_day = Values( name )
    if chw in username_counts:
        for daily_count in username_counts[chw]:
            # values are tuples of dates and daily counts
            values_per_day.append( (date.strftime("%Y-%m-%d"), daily_count) )
            date = date + day
    else:
        # should return a set of '0s' even when no forms submitted
        timespan = get_timespan(start_date, end_date)
        for i in range(0,timespan.days+1):
            values_per_day.append( (date.strftime("%Y-%m-%d"), 0) )
            date = date + day
    values_per_day.run_stats(stats)
    return values_per_day
    
