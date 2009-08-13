""" Data structures to store CommCareHQ reports """

class Report(object):
    """ This class is a generic object for representing data
    intended for specific reports. It is mostly useful so that
    we can transform these structures arbitrarily into xml,
    csv, json, etc. without changing our report generators
    
    """
    
    def __init__(self, title=''):
        self.title = title
        self.generating_url = ''
        # should be a list of DataSets
        self.datasets = []
        
    def __unicode__(self):
        string = "Report: " + unicode(self.title) + "\n"
        for dataset in self.datasets:
            string = string + unicode(dataset)
        return string + "\n\n"
    
    def __str__(self):
        return unicode(self)
    
class DataSet(object):
    """ represents a set or multiple sets of data 
    with a common index (x-axis). So, for example, one dataset
    could be composed of registrations per x, visits per x,
    closures per x, etc. (x being the same for all sets)
    
    """
    
    def __init__(self, name=''):
        self.name = name
        self.params = {}
        # should be a list of valuesets
        self.valuesets = []
        self.indices = ''
    
    def __unicode__(self):
        string = "DataSet: " + unicode(self.name) + "\n"
        for valueset in self.valuesets:
            for value in valueset:
                string = string + " " + unicode(value) + "\n"
            string = string + "\n\n"
        return string

class Values(list):
    """ represents a set of index/value pairs """
    def __init__(self, name=''):
        self.stats = {}
        # indices are determined on a per-dataset basis
        self.name = name

    def run_stats(self, stats):
        """ calculates statistics
        
        stats: specifies the statistics to return
        Given a list of requested statistics, this function populates 
        self.stats with the computed values. Currently we only support 'sum',
        but one can imagine supporting std dev, mean, variance, etc.
        
        """
        
        if not stats: return
        for stat in stats:
            if stat == 'sum':
                sum = 0
                for v in self:
                    sum = sum + long(v[-1])
                self.stats[stat] = sum
