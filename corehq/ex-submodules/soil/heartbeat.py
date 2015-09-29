from django.conf import settings
from datetime import datetime, timedelta
from django.core.cache import cache

NOT_FOUND = "None found"
NOT_CONFIGURED = "Not configured."
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def heartbeat_enabled():
    return hasattr(settings, "SOIL_HEARTBEAT_FILE") or \
           hasattr(settings, "SOIL_HEARTBEAT_CACHE_KEY")

def is_alive(window=timedelta(minutes=10)):
    hb = last_heartbeat()
    return hb and (datetime.utcnow() - window) < hb

def write_file_heartbeat():
    """
    Writes the current time to a file. Returns true if written.
    """
    if hasattr(settings, "SOIL_HEARTBEAT_FILE"):
        with open(settings.SOIL_HEARTBEAT_FILE, 'w') as f:
            f.write(datetime.utcnow().strftime(DATE_FORMAT))
            return True

def write_cache_heartbeat():
    """
    Writes the current time to the cache. Returns true if written.
    """
    if hasattr(settings, "SOIL_HEARTBEAT_CACHE_KEY"):
        cache.set(settings.SOIL_HEARTBEAT_CACHE_KEY, datetime.utcnow().strftime(DATE_FORMAT))
    
def get_file_heartbeat():
    if hasattr(settings, "SOIL_HEARTBEAT_FILE"):
        try:
            with open(settings.SOIL_HEARTBEAT_FILE, 'r') as f:
                return f.read()
        except IOError:
            return NOT_FOUND
    else:
        return NOT_CONFIGURED
    
def get_cache_heartbeat():
    if hasattr(settings, "SOIL_HEARTBEAT_CACHE_KEY"):
        from_cache = cache.get(settings.SOIL_HEARTBEAT_CACHE_KEY) 
        return from_cache if from_cache else NOT_FOUND
    else:
        return NOT_CONFIGURED

def last_heartbeat():
    def _date_or_none(val):
        if val and val != NOT_FOUND and val != NOT_CONFIGURED:
            return datetime.strptime(val, DATE_FORMAT)
        return None
    
    from_file = _date_or_none(get_file_heartbeat())
    from_cache = _date_or_none(get_cache_heartbeat())
    if from_file and from_cache:
        return from_file if from_file > from_cache else from_cache
    elif from_file:
        return from_file
    elif from_cache:
        return from_cache
    else:
        return None
