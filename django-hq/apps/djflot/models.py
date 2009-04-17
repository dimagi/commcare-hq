from django.db import models
from django.contrib.auth.models import Group, User
from django.utils.translation import ugettext_lazy as _
from django.db import connection, transaction, DatabaseError

# Create your models here.


XAXIS_DISPLAY_TYPES = (
    ('date', 'Date'),
    ('numeric', 'Numeric'),
    ('string', 'String'),    
)

CHART_DISPLAY_TYPES = (
    ('absolute-line', 'Absolute Line'),
    ('cumulative-line', 'Cumulative Line'),
    
    ('absolute-bar', 'Absolute Bar'),
    ('cumulative-bar', 'Cumulative Bar'),
    
    ('histogram-trend', 'Histogram Trend'),
    ('histogram', 'Overall Histogram'),
    
)



class RawGraph(models.Model):    
    shortname = models.CharField(max_length=32)
    title = models.CharField(max_length=128)
    table_name = models.CharField(max_length=255)
    
    data_source = models.CharField(_('Database source'),max_length=128, null=True, blank=True, help_text=_("Placeholder for alternate database"))
    db_query = models.TextField(_('Database Query'), help_text=_("Database query that has at least 2 columns returned, the first one being the X axis, and the subsequent ones being the Y axis series"))
        
    x_axis_label = models.CharField(_('X axis label'),max_length=34, help_text=_("Column 0 of the query will use this label")) 
    x_type = models.CharField(max_length=24,choices=XAXIS_DISPLAY_TYPES)
    
    series_labels = models.CharField(_('Series labels'),max_length=34, help_text=_("Each subsequent column in the query will be its own series.  Enter their names separated by the | symbol."))
    display_type = models.CharField(max_length=24,choices=CHART_DISPLAY_TYPES)
    
    series_options = models.CharField(_('Series display options'),max_length=255, blank=True, null=True)
    
    
    #Non Django
    _cursor = None    
            
    class Meta:
        ordering = ('-shortname',)
        verbose_name = _("Raw Graphing Requestor")        
    
    def __unicode__(self):
        return "RawGraph: " + unicode(self.shortname)
    
    @property
    def cursor(self):
        if self._cursor == None:
            self._cursor = connection.cursor()
            self._cursor.execute(self.db_query)
        return self._cursor
    
    def reset(self):
        self._cursor = None    
    
    def get_dataset(self):
        """Execute the query and get the fracking dataset in flot format"""        
        rows = self.cursor.fetchall()
        return rows
    
    def check_series(self):
        cols = self.cursor.description
        
        if len(cols) < 2:
            raise Exception("Error, query did not return enough columns.  You need at least 2")
        else:
            return len(cols)-1
        
    
    def get_dataseries(self):
        rows = self.get_dataset()
        ret = {}
        num_series = self.check_series()
        for i in range(0,num_series):
            ret[i] = []
        
        for row in rows:
            xcol = row[0]
            series_count = 0            
            for ycol in row[1:]:
                ret[series_count].append([xcol,ycol])
                series_count= series_count+1 
            
        return ret
    
    
    
    
    