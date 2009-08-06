

class Report(object):
    """ This class is a generic object for representing data
    intended for specific reports. It is mostly useful so that
    we can arbitrarily change our api from xml to csv, json, etc.
    
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

class Statistics(object):
    def __init__(self, dataset):
        self.dataset = dataset
        self.stats = {}
    
    def get_stats(self, stat_name=None):
        if stat_name==None:
            pass
            # return all stats
        if stat_name=='sum':
            self.stats['sum'] = sum(dataset)
            return self.stats
