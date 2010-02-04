from django.db import models
from django.contrib.auth.models import Group, User
from django.utils.translation import ugettext_lazy as _
from django.db import connection, transaction, DatabaseError
import graphing.dbhelper as dbhelper
import time
import logging
import datetime
from django.utils import simplejson

import re

# Create your models here.


XAXIS_DISPLAY_TYPES = (
    ('date', 'Date'),
    ('MM/DD/YYYY', 'MM/DD/YYYY'),
    ('numeric', 'Numeric'),
    ('string', 'String'),    
)

CHART_DISPLAY_TYPES = (
    ('absolute-line', 'Absolute Line'),
    ('cumulative-line', 'Cumulative Line'),
    
    ('absolute-bar', 'Absolute Bar'),
    ('cumulative-bar', 'Cumulative Bar'),
        
    ('histogram-overall', 'Overall Histogram'),
    ('histogram-multifield', 'Multifield Histogram'),
    ('histogram-multifield-sorted', 'Multifield Histogram (sorted)'),
    
    ('compare-trend', 'Field Compare'),
    ('compare-cumulative', 'Field Compare Cumulative'),    
)


class BaseGraph(models.Model):
    shortname = models.CharField(max_length=32)
    title = models.CharField(max_length=128)
    
    def __unicode__(self):
        return unicode(self.shortname)
    class Meta:
        ordering = ('-id',)
    

class RawGraph(BaseGraph):    
    table_name = models.CharField(max_length=255)
    
    data_source = models.CharField(_('Database source'),max_length=128, null=True, blank=True, help_text=_("Placeholder for alternate database"))
    db_query = models.TextField(_('Database Query'), help_text=_("Database query that has at least 2 columns returned, the first one being the X axis, and the subsequent ones being the Y axis series.  You can also use the special tags: {domain}}, {{startdate}}, and {{enddate}} to provide filtered queries"))
        
    y_axis_label = models.CharField(_('Y axis label'),max_length=128, help_text=_("Label to use for the Y axis"), blank=True, null=True) 
    x_axis_label = models.CharField(_('X axis label'),max_length=128, help_text=_("Column 0 of the query will use this label"), blank=True, null=True) 
    x_type = models.CharField(max_length=32,choices=XAXIS_DISPLAY_TYPES)
    
    series_labels = models.CharField(_('Series labels'),max_length=255, help_text=_("Each subsequent column in the query will be its own series.  Enter their names separated by the | symbol."))
    display_type = models.CharField(max_length=32,choices=CHART_DISPLAY_TYPES)
                                    
    time_bound = models.NullBooleanField(null=True, blank=True, default=False)
    default_interval = models.IntegerField(_('Default Interval'),
                                             default=0,
                                             help_text=_("The date initial date range that will be selected in the UI, in days."))
    interval_ranges = models.CharField(_('Interval Ranges'),
                                   max_length=255, 
                                   null=True, 
                                   blank=True, 
                                   help_text=_("The date interval choices to display in the UI.  Each range should be specified in days separated by the | symbol. For example, 7|30|365 will show options for 1 week, 1 month, and 1 year."))
    
    additional_options = models.CharField(_('Additional display options'),max_length=255, blank=True, null=True,
                                      help_text=_('Any additional options for the charts.  These should be specified as JSON-style entries in a dictionary.  E.g.: {"legend": { "show": false }}'))
    width=models.IntegerField(_('Pixel width of the chart (default is 950)'),default=950)
    height=models.IntegerField(_('Pixel height of the chart (default is 300 for small form factor screens)'), default=300)
    
    #Non Django
    _cursor = None
    helper_cache = {}
    
            
    class Meta:
        ordering = ('-id',)
        verbose_name = _("Raw Graphing Requestor")        
    
    def __unicode__(self):
        return self.shortname
    
    @property
    def date_range_list(self):
        if self.interval_ranges:
            return [int(val) for val in self.interval_ranges.split("|")]
        else:
            # default to some reasonable values
            return [0,7,30,90,365]
    
    @property 
    def cleaned_query(self):
        '''The same as db_query, but with any templated arguments
           filled in.  This is what should be used whenever we actually
           go to the database or try to display the query to the user'''
        try:
            reg = re.compile('(\{\{.*?\}\})')
            query = self.db_query
            matches = reg.findall(self.db_query)
            if matches:
                for match in matches:
                    attr = match[2:len(match)-2]
                    repl = getattr(self,attr)
                    query = query.replace(match, repl)
            return query 
        except Exception, e:            
            logging.error("error cleaning query", extra={'exception':e, 'query':self.db_query})
        return self.db_query
        
    @property
    def cursor(self):        
        # caching the cursor can have some unexpected results if 
        # you fetch from it more than once, so removing this 
        # behavior.  we may want to revisit this if performance
        # becomes an issue
        #if self._cursor == None:
        self._cursor = connection.cursor()
        self._cursor.execute(self.cleaned_query.__str__())        
        return self._cursor    
    
    def reset(self):
        self._cursor = None    
    
    @property
    def has_errors(self):
        try:
            self.reset()
            cursor = self.cursor
            self.reset()
            return False
        except Exception, e:
            extra = {'exception':e}
            logging.error("Error, rawgraph " + str(self) + " query error",extra=extra)
            return True
    
    def get_dataset(self):
        """Execute the query and get the fracking dataset in flot format"""        
        try:
            rows = self.cursor.fetchall()            
            return rows
        except Exception, e:
            args = []
            extra = {"exception": e, "query": self.cleaned_query}            
            logging.log(logging.ERROR,"Error in doing sql query", extra=extra)       
            raise                 
                      
    
    @property
    def labels(self):
        labelarr = self.series_labels.split('|')
        query_cols = self.cursor.description
        labels = []
        # If the label is explicitly specified in the string, use that,
        # otherwise back it out from the query description.  Assumes that
        # if not all labels are explicitly set in the string, the ones that
        # are set are the first N
        for i in range(len(query_cols)):
            if i < len(labelarr):
                labels.append(str(labelarr[i]))
            else:
                labels.append(str(query_cols[i][0]))
        return labels
        
    
    def check_series(self):
        cols = self.cursor.description
        if len(cols) < 2:
            raise Exception("Error, query did not return enough columns.  You need at least 2")
        elif 'histogram-multifield' in self.display_type:
            return len(cols)
        else:
            return len(cols)-1        
        
    def _clean_xcol(self, xval):
        #ugly hack to just clean the columns.
        #right now the dates are being stored as strings in the db, 
        #hence the necessity to do this type of conversinos
        #also, for the ticks in python we need to convert the ticks 
        #by 1000 for javascript to understand them (no milliseconds)
        if self.x_type == 'date':
            if isinstance(xval, datetime.datetime):
                return 1000 * time.mktime(xval.timetuple())                
            else:
                return  1000* time.mktime(time.strptime(str(xval[0:-4]),dbhelper.XMLDATE_FORMAT))
        elif self.x_type == 'MM/DD/YYYY':            
            return 1000*time.mktime(time.strptime(str(xval),dbhelper.MMDDYYYY_FORMAT))
        else:
            return xval.__str__()
  
    def _clean_ycol(self, yval):
        if yval == None:
            return 0
        else:
            return int(yval)

    def get_xaxis_options(self):
        ret = {}
        if self.x_type == 'date' or self.x_type == 'MM/DD/YYYY':
            # format to display pretty dates
            ret['mode'] = 'time'
            ret['timeformat'] = "%m/%d/%y"
        elif self.x_type == 'string':
            # this formats the bottom of the chart
            # to have the appropriate names for histograms
            ticks = self.helper_cache['ticks']
            
            ret["min"] =  0;
            ret['max'] = len(ticks)+2
            
            myticks = []
            
            for i in range(0,len(ticks)):
                myticks.append([i + .5,ticks[i]])
            ret["ticks"] =  myticks
            ret["tickFormatter"] = "string"
            ret['tickDecimals'] = 'null'
        
        else:
            ret['mode'] = 'null'
        
            
        return ret
                
        

    def _get_display_type(self):
        if self.display_type.endswith('line'):
            return "lines"
        elif self.display_type.endswith('bar'):
            return "bars"
        elif self.display_type.startswith('histogram'):
            return "bars"

    def _numeric_dataseries(self,rows):
        ret ={}
        is_cumulative = False
        if self.display_type == 'cumulative-line':
            is_cumulative= True
        num_series = self.check_series()
        for i in range(0,num_series):
            ret[i] = []
        
        cumulative_series = self.check_series()
        series_values= {}
        for i in range(0,cumulative_series):
            series_values[i] = 0
        
        for row in rows:
            xcol = self._clean_xcol(row[0])
            series_count = 0            
            for ycol in row[1:]:
                
                if is_cumulative:
                    ycleaned = self._clean_ycol(ycol)
                    series_values[series_count] = series_values[series_count] + ycleaned 
                    newvalue = series_values[series_count]
                    ret[series_count].append([xcol,newvalue])                    
                else:
                    ret[series_count].append([xcol,self._clean_ycol(ycol)])
                series_count= series_count+1 
        
        return ret
    
    def _multifield_histogram(self, sorted):
        """The multifield histogram expects to get back a dataset
           with a single row of counts specified.  It gets the 
           labels from either the dataset or what is specified in 
           the graphing object.  If sorted is true it will sort 
           the data by count, descending."""
        rows = self.get_dataset()
        if len(rows) != 1:
            raise Exception("Multifield histogram returned the wrong number rows!  Expects 1 but was %s" % len(rows))
        data = rows[0]
        ret = {}        
        num = 0
        self.helper_cache['ticks'] = []
        labels = self.labels
        combined_data = zip(data, labels)
        if sorted:
            # sort by count descending
            combined_data.sort(lambda x, y: int(y[0]) - int(x[0]))
        num_series = len(combined_data)
        for i in range(0,num_series):
            item, label = combined_data[i]
            item = str(item)
            self.helper_cache['ticks'].append(label)            
            count = int(item)
            ret[i] = {}
            ret[i]['label'] = label
            ret[i]['data'] = [[num,count]]
            ret[i]['bars'] = {'show':'true'}
            num = num + 1
        return ret

    
    def _overall_histogram(self):
        
        rows = self.get_dataset()
        ret = {}        
        num = 0
        self.helper_cache['ticks'] = []
        for row in rows:
            item = self._clean_xcol(row[0])
            self.helper_cache['ticks'].append(item)
            
            count = int(row[1])
            
            ret[item] = {}
            ret[item]['label'] = item
            ret[item]['data'] = [[num,count]]
            ret[item]['bars'] = {'show':'true'}
            num = num + 1         
        return ret
    
    def _compare_trends(self):        
        rows = self.get_dataset()        
        ret = {}        
        num = 0
        
                
        is_cumulative = False        
        if self.display_type == 'compare-cumulative':
            is_cumulative= True
            total_hash = {}
        
        for row in rows:            
            xval = self._clean_xcol(row[0])
            indicator = row[1].__str__()
            count = int(row[2])            
            if not ret.has_key(indicator):
                ret[indicator] = {}
                ret[indicator]['label'] = indicator
                ret[indicator]['data'] = []
                
                if is_cumulative:
                    total_hash[indicator] = 0
                    ret[indicator]['lines'] = {'show':'true'}
                    ret[indicator]['points'] = {'show':'false'}
                else:
                    ret[indicator]['lines'] = {'show':'false'}
                    ret[indicator]['points'] = {'show':'true'}
                
                    
            
            if is_cumulative:
                total_hash[indicator] = total_hash[indicator] + count
                ret[indicator]['data'].append([xval,total_hash[indicator]])
            else:
                ret[indicator]['data'].append([xval,count])
                                                 
        return ret
        
    def graph_options(self):
        ret = {}
        ret['yaxis'] = {'min':0}
        ret['xaxis'] = self.get_xaxis_options()
        if self.additional_options:
            options_dict = simplejson.loads(self.additional_options)
            for key in options_dict:
                to_use = {}
                if key in ret:
                    # if we already had some options, use those
                    # as a starting point
                    to_use = ret[key]
                for inner_key, value in options_dict[key].items():
                    to_use[str(inner_key)] = value
                ret[str(key)] = to_use
        # json serialize this so false and unicode values
        # show up properly
        return simplejson.dumps(ret)
    
    def get_dataseries(self):
        rows = self.get_dataset()
        return self._numeric_dataseries(rows)

    
    def get_flot_data(self):
        '''This is the main place where data is obtained for viewing.
           From the information in this chart, get the javascript/JSON 
           object that will allow the chart to be plotted by flot.'''
        try:  
            if self.display_type == 'histogram-overall':
                to_return = self._overall_histogram()
            elif self.display_type == 'histogram-multifield':
                to_return = self._multifield_histogram(False)
            elif self.display_type == 'histogram-multifield-sorted':
                to_return = self._multifield_histogram(True)
            elif self.display_type.startswith('compare'):
                to_return = self._compare_trends()
            else:
                flot_dict = {}
                labels = self.labels
                data = self.get_dataseries()        
                for label in labels:            
                    currseries = {}            
                    currseries["label"] = label.__str__()
                    currseries["data"] = data[labels.index(label)]
                    currseries[self._get_display_type()] = {'show': 'true'}                           
                    flot_dict[label.__str__()] = currseries
                
                to_return = flot_dict
            return to_return
        except Exception, e:                
            extra = {'exception':e, 'graphobject':self, 'display_type':self.display_type, 'table_name':self.table_name, 'db_query':self.db_query}
            logging.error("Error rendering flot data: %s" % e.message,extra=extra)
            return {}
        
        
    def get_data_as_table(self): 
        '''Get the data for this chart in a tabular, dictionary-like
        format.  See also convert_data_to_table.'''
        return self.convert_data_to_table(self.get_flot_data())
    
    def convert_data_to_table(self, flot_data):
        '''An alteration of the data, we want to return all the data 
           in this chart as a pretty little table.'''
        data_dict = flot_data
        # we are gonna make a hash, keyed by the x values
        # within each value of that it's a hash by series
        if self.display_type.startswith('histogram-overall'):
            retarr = []
            retarr.append(['Item','Count'])
            series = data_dict.keys()
            for item in series:
                retarr.append([item,data_dict[item]['data'][0][1]])
            return retarr
        elif "histogram-multifield" in self.display_type:
            labels = []
            data = []
            for key, graph_data in flot_data.items():
                labels.append(graph_data['label'])
                data.append(graph_data['data'][0][1])
            return [labels, data]
        series = data_dict.keys()        
        xvalue_dict = {}        
        xlabel_dict = {}
        for ser in series:
            thedata = data_dict[ser]["data"]        
            for xyarr in thedata:
                
                xlabel = xyarr[0]
                if self.x_type == 'date' or self.x_type == 'MM/DD/YYYY':
                    xlabel = time.strftime(dbhelper.MMDDYYYY_FORMAT,time.localtime(xlabel/1000))               
                
                if not xvalue_dict.has_key(xyarr[0]):    
                    xlabel_dict[xyarr[0]]= xlabel        
                    xvalue_dict[xyarr[0]] = {}
                    for subser in series:                    
                        xvalue_dict[xyarr[0]][subser] = 0                                    
                xvalue_dict[xyarr[0]][ser] = xyarr[1]
    
                    
        xvals = xvalue_dict.keys()    
        xvals.sort()
        
        retarr = []
        retarr.append(['Values'] + series)        
        for xval in xvals:
            rowarr = [xlabel_dict[xval]]
            for ser in series:            
                rowarr.append(xvalue_dict[xval][ser])
            retarr.append(rowarr)
        return retarr
                
                
            
            
        
        
        
        #ok, 2 steps here.
        #first, establish the "columns" or the series here
        #second, establish buckets for what we're trying to display
        #if it's dates, make a global list of all the buckets in use
        #then populate them
        
        
            
        
        
    
    
class GraphGroup(models.Model):
    name = models.CharField(max_length=128)    
    description = models.CharField(max_length=255)    
    graphs = models.ManyToManyField(BaseGraph, blank=True, null=True)
    parent_group = models.ForeignKey('self',null=True,blank=True)
    
    def __unicode__(self):
        return unicode(self.name)
    
    def num_graphs(self):
        return self.graphs.count()
    
class GraphPref(models.Model):
    user = models.ForeignKey(User)
    root_graphs = models.ManyToManyField(GraphGroup,limit_choices_to ={'parent_group':None})
    
    def num_groups(self):
        return self.root_graphs.count()

    def __unicode__(self):
        return u"GraphPref: " + unicode(self.user.username)
    
    