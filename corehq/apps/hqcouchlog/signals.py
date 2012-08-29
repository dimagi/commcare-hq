from couchlog.signals import couchlog_created

def add_hq_extras(record, **kwargs):
    """
    Adds the domain to the couchlog item so that it can be later analyzed.
    """
    if "/a/" in record.url:
        # this is a normal browser 500 errorx
        record.domain = record.url.split("/a/")[1].split("/")[0]
        record.save()
    elif "/a/" in record.message:
        # this match is a bit sketchier, but couchforms has been designed
        # to put the path in the message which is what we're trying to catch
        # here
        record.domain = record.message.split("/a/")[1].split("/")[0]
        record.save()
        
couchlog_created.connect(add_hq_extras) 
