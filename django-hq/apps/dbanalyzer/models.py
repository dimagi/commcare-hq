from django.db import models
from django.contrib.auth.models import Group, User
from django.utils.translation import ugettext_lazy as _
from django.db import connection, transaction, DatabaseError
import dbanalyzer.dbhelper as dbhelper
import time
import logging
import datetime

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
    
    ('compare-trend', 'Field Compare'),
    ('compare-cumulative', 'Field Compare Cumulative'),    
)


class BaseGraph(models.Model):
    shortname = models.CharField(max_length=32)
    title = models.CharField(max_length=128)
    
    def __unicode__(self):
        return "Graph: " + unicode(self.shortname)
    class Meta:
        ordering = ('-id',)
    

class RawGraph(BaseGraph):    
#    shortname = models.CharField(max_length=32)
#    title = models.CharField(max_length=128)
    table_name = models.CharField(max_length=255)
    
    data_source = models.CharField(_('Database source'),max_length=128, null=True, blank=True, help_text=_("Placeholder for alternate database"))
    db_query = models.TextField(_('Database Query'), help_text=_("Database query that has at least 2 columns returned, the first one being the X axis, and the subsequent ones being the Y axis series"))
        
    x_axis_label = models.CharField(_('X axis label'),max_length=128, help_text=_("Column 0 of the query will use this label"), blank=True, null=True) 
    x_type = models.CharField(max_length=32,choices=XAXIS_DISPLAY_TYPES)
    
    series_labels = models.CharField(_('Series labels'),max_length=255, help_text=_("Each subsequent column in the query will be its own series.  Enter their names separated by the | symbol."))
    display_type = models.CharField(max_length=32,choices=CHART_DISPLAY_TYPES)
    
    series_options = models.CharField(_('Series display options'),max_length=255, blank=True, null=True)
    
    
    #Non Django
    _cursor = None
    helper_cache = {}
    
            
    class Meta:
        ordering = ('-id',)
        verbose_name = _("Raw Graphing Requestor")        
    
    def __unicode__(self):
        return "RawGraph: " + unicode(self.shortname)
    
    @property
    def cursor(self):        
        if self._cursor == None:
            self._cursor = connection.cursor()
            self._cursor.execute(self.db_query.__str__())        
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
            logging.error("Error, rawgraph " + str(self) + " has a query error: " + str(e))
            return True
    
    def get_dataset(self):
        """Execute the query and get the fracking dataset in flot format"""        
        try:
            rows = self.cursor.fetchall()            
            return rows
        except Exception, e:
            logging.error("Error in doing sql query %s: %s" % (self.db_query, str(e)))       
            raise                 
                      
    
    @property
    def labels(self):
        labelarr = self.series_labels.split('|')
        if len(labelarr) != self.check_series():
            raise Exception("Error, improperly configured graph labels. They must match exactly with the number of columns returned from the query")
        return labelarr
    
    def check_series(self):
        cols = self.cursor.description
        
        if len(cols) < 2:
            raise Exception("Error, query did not return enough columns.  You need at least 2")
        else:
            return len(cols)-1        
        
    def __clean_xcol(self, xval):
        #ugly hack to just clean the columns.
        #right now the dates are being stored as strings in the db, hence the necessity to do this type of conversinos
        #also, for the ticks in python we need to convert the ticks by 1000 for javascript to understand them (no milliseconds)
        if self.x_type == 'date':
            if isinstance(xval, datetime.datetime):
                return 1000 * time.mktime(xval.timetuple())                
            else:
                return  1000* time.mktime(time.strptime(str(xval[0:-4]),dbhelper.XMLDATE_FORMAT))
        elif self.x_type == 'MM/DD/YYYY':            
            return 1000*time.mktime(time.strptime(str(xval),dbhelper.MMDDYYYY_FORMAT))
        else:
            return xval.__str__()
  
    def __clean_ycol(self, yval):
        if yval == None:
            return 0
        else:
            return int(yval)

    def get_xaxis_options(self):
        ret = {}
        
        if self.x_type == 'date' or self.x_type == 'MM/DD/YYYY':
            ret['mode'] = 'time'
            ret['timeformat'] = "%m/%d/%y"
        elif self.x_type == 'string':
            ticks = self.helper_cache['ticks']
            
            ret["min"] =  0;
            ret['max'] = len(ticks)+2
            #rootxaxis.put("max", tickvalues.length + tickvalues.length / 5 + 1);
            
            myticks = []
            
            for i in range(0,len(ticks)):
                myticks.append([i,ticks[i]])
            ret["ticks"] =  myticks
#            ret["ticksize"] =  len(ticks)
            ret["tickFormatter"] = "string"
            ret['tickDecimals'] = 'null'
        
        else:
            ret['mode'] = 'null'
        
            
        return ret
                
        

    def __get_display_type(self):
        if self.display_type.endswith('line'):
            return "lines"
        elif self.display_type.endswith('bar'):
            return "bars"
        elif self.display_type.startswith('histogram'):
            return "bars"

    def __numeric_dataseries(self,rows):
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
            xcol = self.__clean_xcol(row[0])
            series_count = 0            
            for ycol in row[1:]:
                
                if is_cumulative:
                    ycleaned = self.__clean_ycol(ycol)
                    series_values[series_count] = series_values[series_count] + ycleaned 
                    newvalue = series_values[series_count]
                    ret[series_count].append([xcol,newvalue])                    
                else:
                    ret[series_count].append([xcol,self.__clean_ycol(ycol)])
                series_count= series_count+1 
        
        return ret
    
    def __multifield_histogram(self):
        rows = self.get_dataset()
        ret = {}        
        num = 0
        self.helper_cache['ticks'] = []
        num_series = self.check_series()
        for i in range(0,num_series):            
            # (count, count,count, count)            
            item = self.__clean_xcol(row[0][i])
            self.helper_cache['ticks'].append(item)            
            count = int(row[0][i])
            
            ret[item] = {}
            ret[item]['label'] = item
            ret[item]['data'] = [[num,count]]
            ret[item]['bars'] = {'show':'true'}
            num = num + 1         
        return ret

    
    def __overall_histogram(self):
        rows = self.get_dataset()
        ret = {}        
        num = 0
        self.helper_cache['ticks'] = []
        for row in rows:
            # (username, count)            
            item = self.__clean_xcol(row[0])
            self.helper_cache['ticks'].append(item)
            
            count = int(row[1])
            
            ret[item] = {}
            ret[item]['label'] = item
            ret[item]['data'] = [[num,count]]
            ret[item]['bars'] = {'show':'true'}
            num = num + 1         
        return ret
    
    def __compare_trends(self):        
        rows = self.get_dataset()        
        ret = {}        
        num = 0
        
                
        is_cumulative = False        
        if self.display_type == 'compare-cumulative':
            is_cumulative= True
            total_hash = {}
        
        for row in rows:            
            xval = self.__clean_xcol(row[0])
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
        #{ yaxis: {     min: 0 }, xaxis: { mode: {{rawgraph.get_xaxis_rendermode()}}}}
        ret = {}
        ret['yaxis'] = {'min':0}
        ret['xaxis'] = self.get_xaxis_options()
        return ret
    
    def get_dataseries(self):
        rows = self.get_dataset()
        return self.__numeric_dataseries(rows)

    
    def get_flot_data(self):      
        try:  
            if self.display_type == 'histogram-overall':
                return self.__overall_histogram()
            elif self.display_type.startswith('compare'):
                return self.__compare_trends()
            else:
                flot_dict = {}
                labels = self.labels
                data = self.get_dataseries()        
                for label in labels:            
                    currseries = {}            
                    currseries["label"] = label.__str__()
                    currseries["data"] = data[labels.index(label)]
                    currseries[self.__get_display_type()] = {'show': 'true'}                           
                    flot_dict[label.__str__()] = currseries
                
                
                #return '{"demo":{"label":"test", "data": [[0,1],[1,2],[2,1],[3,10],[4,5]]}}'
                return flot_dict
        except Exception, e:
            logging.error("Error rendering flot data: " + str(e))
            return '[]'
            
        
        
    
    
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
    
    