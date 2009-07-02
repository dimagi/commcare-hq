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

from dbanalyzer.models import RawGraph

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
    ret = ""
    for fdef in defs:
        try: 
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
        except Exception, e:
            # this shouldn't blow up the entire view
            logging.error("problem in dashboard display: %s" % e)
            ret += '<p style="font-weight:bold; color:red;">problem in dashboard display.  Not all data will be visible.  Your error message is: %s</p>' % e
            
    # this block generates the table definition, and headers (one for each
    # user).  It also populates the hash of date-->count mappings per user
    # to be displayed in the next loop.
    ret += '<table class="sofT">\n<thead class="commcare-heading"><tr><th>Date</th>'
    for user in username_to_count_hash.keys():
        ret += '<th>%s</th>' % (user)
        for datestr in username_to_count_hash[user].keys():
            #dt = time.strptime(str(datestr[0:-4]),xmldate_format)
            #datum = datetime(dt[0],dt[1],dt[2],dt[3],dt[4],dt[5],dt[6])
            #date = datum.strftime('%m/%d/%Y')              
            if not report_hash[datestr].has_key(user):
                report_hash[datestr][user]=username_to_count_hash[user][datestr]
    ret += "</tr></thead>\n"
    count = 1
    for day in range(0,totalspan.days+1):
        delta = timedelta(days=day)
        target_date = startdate + delta
        date = target_date.strftime('%m/%d/%Y')
        if count % 2 == 0:
            row_class = "even"
        else: 
            row_class = "odd"
        count += 1 
        ret += '<tr class="%s">' % row_class
        ret += "<td>%s</td>" % (date)
        for user in username_to_count_hash.keys():
            val = 0
            if report_hash[date].has_key(user):
                val = report_hash[date][user]
            ret += "<td>%d</td>" % (val)
        ret += "</tr>\n"
    ret += "</table>"
    username_to_count_hash.clear()
    
    
    # add the chart.  this might be a bit hacky, but we're going 
    # to try using render_to_string and inline_rawgraph to return 
    # this with the tag
    try:
        chart = RawGraph.objects.get(title="CHW Submissions Over Time")
        chart.domain = extuser.domain.name
        chart.startdate = startdate.strftime("%Y-%m-%d")
        chart.enddate = (enddate + timedelta(days=1)).strftime("%Y-%m-%d")
        chart_display = render_to_string("dbanalyzer/inline_rawgraph.html", {"chart" : chart, "width" : 900, "height": 500})
        # czue commenting this out until the chart is less ugly 
        # ret += chart_display
    except RawGraph.DoesNotExist:
        # they don't have this chart.  Just let it slide
        pass
    except Exception, e:
        logging.error(e)
    return ret

