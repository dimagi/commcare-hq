

class Report(object):
    """ This class is a generic object for representing data
    intended for specific reports. It is mostly useful so that
    we can arbitrarily change our api from xml to csv, json, etc.
    
    """
    def __init__(self, title='', datasets=[]):
        self.title = title
        self.datasets = datasets
        
    def __unicode__(self):
        string = "Report: " + unicode(self.name) + "\n"
        for dataset in self.datasets:
            string = string + unicode(dataset)
        return string + "\n\n"
    
class DataSet(object):
    """ represents a generic dataset """
    def __init__(self, name='', params={}, stats={}, entries=[]):
        self.name = name
        self.params = params
        self.stats = stats
        self.entries = entries
    
    def __unicode__(self):
        string = "DataSet: " + unicode(self.title) + "\n"
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
