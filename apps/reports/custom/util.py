"""
Utility functions for custom reports
"""
from datetime import datetime, timedelta
from xformmanager.models import Metadata

def forms_submitted(reporter_profile, days=0, weeks=0, hours=0):
    """
    timeframe - the period of time during which these forms were submitted
    
    returns a count of the number of forms submitted over the given timeframe
    """
    metas = Metadata.objects.filter(username=reporter_profile.chw_username)
    delta = timedelta(days=days, weeks=weeks, hours=hours)
    since = datetime.now() - delta
    metas = metas.filter(attachment__submission__submit_time__gte=since)
    return metas.count()


