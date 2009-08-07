

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

def get_stats(stats, entries):
    """ gets statistics
    
    stats: specifies the statistics to return
    entries: tuples with the second value a number no bigger than a Long
    This function returns a dictionary of the requested statistics
    """

    ret = {}
    if not stats:
        return stats
    for stat in stats:
        if stat == 'sum':
            sum = 0
            for e in entries:
                sum = sum + long(e[1])
            ret[stat] = sum
        # this function can be expanded to cover a variety of stats
    return ret

def get_params(request):
    """ gets parameters
    
    request: http request object
    This function returns a dictionary of the http GET parameters
    """

    params = {}
    # get the part after '?' in the http request
    for item in request.GET.items():
        params[item[0]] = item[-1]
    return params
