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
        self.datasets = []
        
    def __unicode__(self):
        string = "Report: " + unicode(self.title) + "\n"
        for dataset in self.datasets:
            string = string + unicode(dataset)
        return string + "\n\n"
    
    def __str__(self):
        return unicode(self)
    
class DataSet(object):
    """ represents a generic dataset """
    
    class Entries(list):
        """ represents a collection of index/value pairs """
        def __init__(self):
            list.__init__(self)
            self.index_ = ''
            self.value = ''

    def __init__(self, name=''):
        self.name = name
        self.params = {}
        self.stats = {}
        self.entries = self.Entries()
    
    def __unicode__(self):
        string = "DataSet: " + unicode(self.name) + "\n"
        for entry in self.entries:
            string = string + " " + unicode(entry) + "\n"
        return string
    
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
                for e in self.entries:
                    sum = sum + long(e[-1])
                self.stats[stat] = sum

