from blacklist import blacklist as inner_blacklist
from metadata import metadata as inner_metadata


"""Where to put default global reports.  These behave just like custom reports
   except they are available to all domains.  If you don't want these reports
   to show up for your domain you should create a <domain>.py file in this 
   folder and explicitly point to any reports you want to include."""

# TODO: we have a lot of reports directories and custom/all/default is
# a pretty obnoxious namespace.  Possibly figure out a better way to 
# organize these if it becomes to burdensome

# TODO: there are now two places you have to put these.
# I think we can introspect them from each other, but not going to yet.
# This two-layered thing is prefered to keep this file from getting 
# prohibitively large.   

def blacklist(request, domain=None):
    '''Report of Who is Submitting as Blacklisted Users'''
    return inner_blacklist(request, domain)


def metadata(request, domain=None):
    '''Submission Summary List for All Forms'''
    return inner_metadata(request, domain)