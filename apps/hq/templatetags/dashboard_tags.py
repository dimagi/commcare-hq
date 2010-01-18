from django import template

from django.core.urlresolvers import reverse
from django.template.loader import render_to_string

from django.contrib.contenttypes.models import ContentType
from types import ListType,TupleType

from xformmanager.models import *
import xformmanager.adapter.querytools as qtools
from hq.models import *
import hq.utils as utils
from datetime import timedelta
import graphing.dbhelper as dbhelper
from hq.models import *
register = template.Library()

from graphing.models import RawGraph

import time

xmldate_format= '%Y-%m-%dT%H:%M:%S'
output_format = '%Y-%m-%d %H:%M'



@register.simple_tag
def get_dashboard_user_counts(user, startdate=None, enddate=None, use_blacklist=True):
    
    # todo:  query the global meta tables to get all the users
    # and/or query the ExtUser table to get all the registered users.
    totalspan = enddate-startdate
    report_hash = {}
    extuser = ExtUser.objects.get(id=user.id)
    
    for day in range(0,totalspan.days+1):
        delta = timedelta(days=day)
        target_date = startdate + delta
        report_hash[target_date.strftime('%m/%d/%Y')] = {}
    # for now, we're going to get all the users in the system by querying
    # the actual tables for usernames
    defs = FormDefModel.objects.all().filter(domain=extuser.domain)
    ret = ""
    
    username_to_count_hash = { }
    if use_blacklist:
        domain_blacklist = extuser.domain.get_blacklist()
    for fdef in defs:
        try: 
            # don't do anything if we can't find a username column
            username_col = fdef.get_username_column()
            if not username_col:
                logging.warning("No username column found in %s, will not display dashboard data." % fdef)
                ret += '<p style="font-weight:bold; color:orange;">Warning: no username column found in %s, no dashboard data will be displayed for this form</p>' % fdef
                continue
            helper = fdef.db_helper
            # let's get the usernames
            usernames_to_filter = helper.get_uniques_for_column(username_col)
            for user in usernames_to_filter:
                if use_blacklist and user in domain_blacklist:
                    # skip over blacklisted users
                    continue
                if not username_to_count_hash.has_key(user):
                    this_user_hash = {"total" : 0 }
                    # this_user_hash = {}
                else:
                    this_user_hash = username_to_count_hash[user]   
                # we add one to the enddate because the db query is not inclusive.
                userdailies = helper.get_filtered_date_count(startdate, 
                                                             enddate + timedelta(days=1),
                                                             filters={username_col: user})
                for date_count_pair in userdailies:
                    # if there already was a count, we add it to it, otherwise
                    # we set a new count equal to this value
                    if date_count_pair[1] in this_user_hash:
                        this_user_hash[date_count_pair[1]] += int(date_count_pair[0])
                    else:
                        this_user_hash[date_count_pair[1]] = int(date_count_pair[0])
                    # either way it updates the total
                    this_user_hash["total"] += int(date_count_pair[0])
                username_to_count_hash[user] = this_user_hash
        except Exception, e:
            # this shouldn't blow up the entire view
            logging.error("problem in dashboard display: %s" % e)
            ret += '<p style="font-weight:bold; color:red;">problem in dashboard display.  Not all data will be visible.  Your error message is: %s</p>' % e
            
    ret += '''<table>\n<thead><tr>
                <th>Date</th>
                <th>Grand Total</th>'''
    
    # preprocess all users by removing them if they don't have any data at all
    # for the period
    ordered_users = []
    for user in username_to_count_hash:
        if username_to_count_hash[user]["total"]:
           ordered_users.append(user)  
    ordered_users.sort()
    
    # this block generates the table definition, and headers (one for each
    # user).  It also populates the hash of date-->count mappings per user
    # to be displayed in the next loop.
    
    
    total_counts_by_date = {"total": 0}
    for user in ordered_users:
        ret += '\n  <th>%s</th>' % (user)
        for datestr in username_to_count_hash[user].keys():
            if datestr == "total":
                continue
            # czue - why is this check here?  I don't actually think
            # its possible that the key is already there, and if it is
            # it seems like an error.  Leaving for someone else 
            if not report_hash[datestr].has_key(user):
                report_hash[datestr][user]=username_to_count_hash[user][datestr]
            if not datestr in total_counts_by_date:
                total_counts_by_date[datestr] = 0
            total_counts_by_date[datestr] += username_to_count_hash[user][datestr]
            total_counts_by_date["total"] += username_to_count_hash[user][datestr]
    ret += "</tr></thead>\n"
    count = 1
    # first add row for totals
    if totalspan.days >= 0:
        ret += "\n<tr class=%s>" % _get_class(count)
        count += 1
        ret += "<td><b>All Dates Shown</b></td>" 
        ret += "<td><b>%s</b></td>" % (total_counts_by_date["total"])
        for user in ordered_users:
            ret += "<td><b>%s</b></td>" % (username_to_count_hash[user]["total"])
    
    dateranges = range(0,totalspan.days+1)
    dateranges.reverse() 
    for day in dateranges:
        delta = timedelta(days=day)
        target_date = startdate + delta
        date = target_date.strftime('%m/%d/%Y')
        ret += '\n<tr class="%s">' % _get_class(count)
        count += 1 
        ret += "<td>%s</td>" % (date)
        # add total for this date
        if date in total_counts_by_date:
            ret += "<td><b>%s</b></td>" % (total_counts_by_date[date])
        else:
            # we could theoretically append all 0's in one fall swoop here
            # and move on to the next date.  For now just let it be 
            # slightly less efficient and address this as a potential 
            # performance gain
            ret += "<td>0</td>"
        for user in ordered_users:
            val = 0
            if report_hash[date].has_key(user):
                val = report_hash[date][user]
            ret += "<td>%d</td>" % (val)
        ret += "</tr>\n"
    ret += "</table>"
    username_to_count_hash.clear()
    
    append_chart = False
    if append_chart:
        ret += _get_chart_display(extuser.domain, startdate, enddate)
    
    return ret

def _get_chart_display(domain, startdate, enddate):
    # add the chart.  this might be a bit hacky, but we're going 
    # to try using render_to_string and inline_rawgraph to return 
    # this with the tag
    try:
        chart = RawGraph.objects.get(title="CHW Submissions Over Time")
        chart.domain = domain.name
        chart.startdate = startdate.strftime("%Y-%m-%d")
        chart.enddate = (enddate + timedelta(days=1)).strftime("%Y-%m-%d")
        return render_to_string("graphing/inline_rawgraph.html", {"chart" : chart, "width" : 900, "height": 500})
    except RawGraph.DoesNotExist:
        # they don't have this chart.  Just let it slide
        return ""
    except Exception, e:
        logging.error(e)
        return ""
    
def _get_class(count):
    if count % 2 == 0:
        return "even"
    return "odd"
        