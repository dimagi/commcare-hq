from datetime import datetime, timedelta
from django.http import HttpResponseBadRequest
from transformers.xml import xmlify
from transformers.http import responsify
from xformmanager.models import FormDefModel, Metadata
from hq.models import ReporterProfile
from hq.reporter.api_.reports import Report, DataSet, Values
from hq.reporter.metadata import get_username_count

# TODO - clean up index/value once we hash out this spec more properly
# TODO - pull out authentication stuff into some generic wrapper
# if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
#    return HttpResponseBadRequest("You do not have permissions to use this API.")

# <HACK>
# temporary hack for august 6 - TODO: remove
from hq.models import Domain
# </HACK>

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
    _report = get_report(request, ids, index, value, start_date, end_date, stats)
    xml = xmlify(_report)
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
    # TODO - filter returned data by user's domain
    # <HACK>
    # temporary hack to get pf api working. TODO - remove once 
    # we figure out user authentication/login from the mobile phone
    try:
        domain = Domain.objects.get(name='Pathfinder')
    except Domain.DoesNotExist:
        return HttpResponseBadRequest( \
            "Domain 'Pathfinder' does not exist.")    
    # </HACK>
    # this is the correct way to do it. use this in the long term.
    # try:
    #    extuser = ExtUser.objects.get(id=request.user.id)
    # except ExtUser.DoesNotExist:
    #    return HttpResponseBadRequest( \
    #        "You do not have permission to use this API.")
    # domain = extuser.domain
    
    _report = Report("CHW Group Total Activity Report")
    _report.generating_url = request.path
    total_metadata = Metadata.objects.filter(submission__submission__submit_time__gte=start_date)
    total_metadata = total_metadata.filter(submission__submission__submit_time__lte=end_date)
    metadata = total_metadata.filter(formdefmodel__in=ids).order_by('id')
    if not metadata:
        raise Exception("Form with id in %s was not found." % str(ids) )
    
    dataset = DataSet( unicode(value[0]) + " per " + unicode(index) )
    dataset.indices = unicode(index)
    dataset.params = request.GET

    # when 'organization' is properly populated, we can start using that
    #       member_list = utils.get_members(organization)
    # for now, just use domain
    member_list = [r.chw_username for r in ReporterProfile.objects.filter(domain=domain)]
    # get the specified forms
    for id in ids:
        form_per_member = Values( unicode(value[0]) )
        form_metadata = metadata.filter(formdefmodel=id)
        for member in member_list:
            # values are tuples of dates and counts
            form_per_member.append( (member, form_metadata.filter(username=member).count()) )
        form_per_member.run_stats(stats)
    dataset.valuesets.append( form_per_member )
    
    # get a sum of all forms
    visits_per_member = Values( "visits" )
    for member in member_list:
        visits_per_member.append( (member, total_metadata.filter(username=member).count()) )
    visits_per_member.run_stats(stats)
    dataset.valuesets.append( visits_per_member )

    _report.datasets.append(dataset)
    return _report

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
    
    # TODO - filter returned data by user's domain
    # <HACK>
    # temporary hack to get pf api working. TODO - remove once 
    # we figure out user authentication/login from the mobile phone
    try:
        domain = Domain.objects.get(name='Pathfinder')
    except Domain.DoesNotExist:
        return HttpResponseBadRequest( \
            "Domain 'Pathfinder' does not exist.")    
    # </HACK>
    # this is the correct way to do it. use this in the long term.
    # try:
    #    extuser = ExtUser.objects.get(id=request.user.id)
    # except ExtUser.DoesNotExist:
    #    return HttpResponseBadRequest( \
    #        "You do not have permission to use this API.")
    # domain = extuser.domain

    if request.GET.has_key('chw'): chw = request.GET['chw']
    else: raise Exception("This reports requires a CHW parameter")

    # TODO - this currrently only tested for value lists of size 1. test. 
    _report = Report("CHW Daily Activity Report")
    _report.generating_url = request.path
    # when 'organization' is properly populated, we can start using that
    #       member_list = utils.get_members(organization)
    # for now, just use domain    
    member_list = [r.chw_username for r in ReporterProfile.objects.filter(domain=domain)]
    form_list = FormDefModel.objects.filter(pk__in=ids)
    username_counts = get_username_count(form_list, member_list, start_date, end_date)
    if chw not in username_counts:
        raise Exception("Username could not be matched to any submitted forms")
    
    dataset = DataSet( unicode(value[0]) + " per " + unicode(index) )
    dataset.indices = unicode(index)
    dataset.params = request.GET
    
    date = start_date
    day = timedelta(days=1)
    forms_per_day = Values( unicode(value[0]) )
    for daily_count in username_counts[chw]:
        # values are tuples of dates and daily counts
        forms_per_day.append( (date.strftime("%Y-%m-%d"), daily_count) )
        date = date + day
    forms_per_day.run_stats(stats)
    dataset.valuesets.append( forms_per_day )

    # get a sum of all the forms
    member_list = [r.chw_username for r in ReporterProfile.objects.filter(domain=domain)]
    username_counts = get_username_count(None, member_list, start_date, end_date)
    if chw not in username_counts:
        raise Exception("Username could not be matched to any submitted forms")
    date = start_date
    day = timedelta(days=1)
    visits_per_day = Values( 'visits' )
    for daily_count in username_counts[chw]:
        # values are tuples of dates and daily counts
        visits_per_day.append( (date.strftime("%Y-%m-%d"), daily_count) )
        date = date + day
    visits_per_day.run_stats(stats)
    dataset.valuesets.append( visits_per_day )
    
    _report.datasets.append(dataset)      
    return _report

