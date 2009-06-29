from django import template

from django.core.urlresolvers import reverse
from django.template.loader import render_to_string

from django.contrib.contenttypes.models import ContentType
from types import ListType,TupleType

from xformmanager.models import *
import xformmanager.adapter.querytools as qtools
from organization.models import *
import organization.utils as utils
from datetime import timedelta
import dbanalyzer.dbhelper as dbhelper
from organization.models import *
register = template.Library()

import time

xmldate_format= '%Y-%m-%dT%H:%M:%S'
output_format = '%Y-%m-%d %H:%M'



@register.simple_tag
def get_dashboard_user_counts(user, startdate=None, enddate=None):
    username_to_count_hash = {}
    
    #todo:  query the global meta tables to get all the users
    #and/or query the ExtUser table to get all the registered users.
    totalspan = enddate-startdate
    report_hash = {}
    extuser = ExtUser.objects.get(id=user.id)
    
    for day in range(0,totalspan.days+1):
        delta = timedelta(days=day)
        target_date = startdate + delta
        #print target_date.strftime('%m/%d/%Y')
        report_hash[target_date.strftime('%m/%d/%Y')] = {}
    #for now, we're going to get all the users in the system by querying the actual tables for usernames
    defs = FormDefModel.objects.all().filter(domain=extuser.domain)
    
    for fdef in defs:        
        table = fdef.element.table_name
        helper = dbhelper.DbHelper(table, fdef.form_display_name) 
        #let's get the usernames
        # hack!  manually set this for grameen
        usernames_to_filter = helper.get_uniques_for_column('meta_username', None, None)
        if extuser.domain.name == "Grameen":
            usernames_to_filter = ["mustafizurrahmna",
                                   "mdyusufali",
                                   "afrozaakter  ",
                                   "renuaraakter",
                                   "mostshahrinaakter",
                                   "shahanaakter",
                                   "sajedaparvin",
                                   "nasimabegum"
                                   ]
        for user in usernames_to_filter:            
            if not username_to_count_hash.has_key(user):
                username_to_count_hash[user] = {}                        
            # we add one to the enddate because the db query is not inclusive.
            userdailies = helper.get_filtered_date_count(startdate, enddate + timedelta(days=1),filters={'meta_username': user})   
            for dat in userdailies:                
                username_to_count_hash[user][dat[1]] = int(dat[0])

    
    # this block generates the table definition, and headers (one for each
    # user).  It also populates the hash of date-->count mappings per user
    # to be displayed in the next loop.
    ret = '<table class="sofT"><tr><td class="helpHed">Date</td>'
    for user in username_to_count_hash.keys():
        ret += '<td  class="helpHed">%s</td>\n' % (user)
        for datestr in username_to_count_hash[user].keys():
            #dt = time.strptime(str(datestr[0:-4]),xmldate_format)
            #datum = datetime(dt[0],dt[1],dt[2],dt[3],dt[4],dt[5],dt[6])
            #date = datum.strftime('%m/%d/%Y')              
            if not report_hash[datestr].has_key(user):
                report_hash[datestr][user]=username_to_count_hash[user][datestr]
    ret += "</tr>\n"
    
    for day in range(0,totalspan.days+1):
        delta = timedelta(days=day)
        target_date = startdate + delta
        date = target_date.strftime('%m/%d/%Y')
        ret += "<tr>"
        ret += "<td>%s</td>" % (date)
        for user in username_to_count_hash.keys():
            val = 0
            if report_hash[date].has_key(user):
                val = report_hash[date][user]
            ret += "<td>%d</td>" % (val)
        ret += "</tr>\n\n"
    ret += "</table>"
    username_to_count_hash.clear()
    
    
    # add the chart.  this might be a bit hacky, but we're going 
    # to try using render_to_string and inline_rawgraph to return 
    # this with the tag
    # this was a proof of concept.  commenting out the line that actually
    # adds it to the response since we aren't sure we want these displaying
    # on the dashboard yet.
    chart = DummyChart()
    chart.title = "User Submissions"
    chart.has_errors = False
    chart.get_flot_data = "{'demo_user': {'bars': {'show': 'true'}, 'data': [[2, 12]], 'label': 'demo_user'}, 'gayo': {'bars': {'show': 'true'}, 'data': [[3, 15]], 'label': 'gayo'}, 'admin': {'bars': {'show': 'true'}, 'data': [[0, 12]], 'label': 'admin'}, 'brian': {'bars': {'show': 'true'}, 'data': [[1, 35]], 'label': 'brian'}, 'mobile1': {'bars': {'show': 'true'}, 'data': [[4, 12]], 'label': 'mobile1'}, 'mobile3': {'bars': {'show': 'true'}, 'data': [[6, 12]], 'label': 'mobile3'}, 'mobile2': {'bars': {'show': 'true'}, 'data': [[5, 12]], 'label': 'mobile2'}}"
    chart.id = 1
    chart.graph_options = "{'xaxis': {'max': 9, 'tickFormatter': 'string', 'ticks': [[0, 'admin'], [1, 'brian'], [2, 'demo_user'], [3, 'gayo'], [4, 'mobile1'], [5, 'mobile2'], [6, 'mobile3']], 'tickDecimals': 'null', 'min': 0}, 'yaxis': {'min': 0}}"
    chart_display = render_to_string("dbanalyzer/inline_rawgraph.html", {"chart" : chart, "width" : 900, "height": 500})
    #ret += chart_display
    return ret

class DummyChart(object):
    '''This isn't really an object, just having an arbitrary
       class allows us to attach properties and send them in 
       a template.  This is used to render charts, hence the
       name.''' 
    def __init__(self):
        pass