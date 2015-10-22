from django.conf import settings

if settings.PROCESSOR_BACKEND == 'couch':
    from .couch import *
elif settings.PROCESSOR_BACKEND == 'sql':
    from .sql import *
