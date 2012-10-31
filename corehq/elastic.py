import rawes
from django.conf import settings

def get_es():
    """
    Get a handle to the configured elastic search DB
    """
    return rawes.Elastic('%s:%s' % (settings.ELASTICSEARCH_HOST, 
                                    settings.ELASTICSEARCH_PORT))
