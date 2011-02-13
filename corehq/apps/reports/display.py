from dimagi.utils.mixins import UnicodeMixIn
import logging
from django.utils.datastructures import SortedDict

REPORT_TYPES = (("f", "fractional"), ("n", "numeric"))

class ReportDisplayValue(UnicodeMixIn):
    """
    Report Display Value 
    """
    
    slug = ""
    hidden = False
    display_name = ""
    description = ""
    
    def __init__(self, slug, hidden, display_name, description):
        self.slug = slug
        self.hidden = hidden
        self.display_name = display_name
        self.description = description
        
    def __unicode__(self):
        return "%s%s: %s %s" % (self.display_name, 
                                " (%s)" % self.slug if self.slug != self.display_name else "",
                                self.tabular_display, "(hidden)" if self.hidden else "")
    @property
    def tabular_display(self):
        """How this appears in tables"""
        # subclasses should override this
        pass
        
    @property
    def graph_value(self):
        """How this appears in graphs"""
        # subclasses should override this
        pass
        

class NumericalDisplayValue(ReportDisplayValue):
    """
    Report Display Value for numeric fields 
    """
    value = 0

    def __init__(self, value, slug, hidden, display_name, description):
        super(NumericalDisplayValue, self).__init__(slug, hidden, display_name, description)
        self.value = value
            
    
    @property
    def tabular_display(self):
        return str(self.value)
    
    @property
    def graph_value(self):
        return self.value
     
    

class FractionalDisplayValue(ReportDisplayValue):
    """
    Fractional Report Display Value (mirrors the javascript class used in the PI reports)
    """
    num = 0
    denom = 0
    
    def __init__(self, num, denom, slug, hidden, display_name, description):
        super(FractionalDisplayValue, self).__init__(slug, hidden, display_name, description)
        self.num = num
        self.denom = denom
            
    
    @property
    def tabular_display(self):
        if self.denom == 0:
            return "N/A"
        return "%.0f%%  (%s/%s)" % ((float(self.num) / float(self.denom) * 100.0), self.num, self.denom) 
    
    @property
    def graph_value(self):
        if self.denom == 0:
            return "N/A"
        return int(float(self.num) / float(self.denom) * 100.0)
    
    def __unicode__(self):
        return "%s%s: %s (%s/%s) %s" % (self.display_name, 
                                     " (%s)" % self.slug if self.slug != self.display_name else "",
                                     self.tabular_display, self.num, self.denom,
                                     "(hidden)" if self.hidden else "")
     
class ReportDisplayRow(UnicodeMixIn):
    """
    Report displays for a row of data
    """
    name = ""
    values = []
    keys = {}
    _slug_to_values_map = {}
    
    def __init__(self, name, keys, values):
        self.name = name
        self.values = values
        self.keys = keys
        self._slug_to_values_map = {}
    
    
    def __unicode__(self):
        return "%s (%s):\n%s" % (self.name, ", ".join(["%s:%s" %(key,val) for key, val in self.keys.items()]), 
                                     "\n".join([str(val) for val in self.values]))
    
        
    def get_value(self, slug):
        """
        Get a value from the row by slug.
        """
        if slug in self._slug_to_values_map:
            return self._slug_to_values_map[slug]
        else:
            matched_vals = [val for val in self.values if val.slug == slug]
            if len(matched_vals) == 1:
                self._slug_to_values_map[slug] = matched_vals[0]    
                return matched_vals[0]
            else:
                logging.error("%s matches found for %s in %s! Expected only one." % \
                              (len(matched_vals), slug, self))
                return None
        
    @classmethod
    def from_pi_view_results(cls, view_results_row):
        """
        Build a report display row from a couchdb object
        """
        key = view_results_row["key"]
        value = view_results_row["value"]
        month, year = None, None
        if len(key) > 2:
            year, js_month, clinic = key[:3]
            month = js_month + 1
        else:
            raise Exception("Need to fully specify key!")
        report_name = value["name"]
        report_values = value["values"]
        vals = []
        for rep_val in report_values:
            value_display = FractionalDisplayValue(rep_val["num"], rep_val["denom"],
                                                   rep_val["slug"], rep_val["hidden"],
                                                   rep_val["display_name"] if rep_val["display_name"] else rep_val["slug"], 
                                                   rep_val["description"])
            vals.append(value_display)
        
        keys = SortedDict()
        keys["Clinic"] = clinic
        keys["Year"] = year
        keys["Month"] = month
        return ReportDisplayRow(report_name, keys, vals)

class ReportDisplay(UnicodeMixIn):
    """
    The whole report
    """
    
    name = ""
    rows = []
    def __init__(self, name, rows):
        self.name = name
        self.rows = rows 
        
    
    def get_slug_keys(self):
        keys = []
        for row in self.rows:
            for val in row.values :
                if not val.hidden and val.slug not in keys:
                    keys.append(val.slug)
        return keys
    
    def get_display_value_keys(self):
        keys = []
        for row in self.rows:
            for val in row.values :
                if not val.hidden and val.display_name not in keys:
                    keys.append(val.display_name)
        return keys
    
    def get_descriptions(self):
        keys = []
        for row in self.rows:
            for val in row.values :
                if not val.hidden and val.description not in keys:
                    keys.append(val.description)
        return keys
    
    @classmethod
    def from_pi_view_results(cls, results):
        """
        Build a report display row from a couchdb object
        """
        report_name = ""
        display_rows = []
        for row in results:
            row_display = ReportDisplayRow.from_pi_view_results(row)
            display_rows.append(row_display)
            # these are assumed to always be the same so just pick one
            report_name = row_display.name
        return ReportDisplay(report_name, display_rows)
        