"""We put utility code in a separate package so that other tests 
   can use it without triggering this app's unit tests 
"""

import hashlib
from domain.models import Domain, Membership
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from hq.models import ReporterProfile
from reporters.models import Reporter, PersistantConnection

def create_user_and_domain(username='brian', 
                           password='test',
                           domain_name='mockdomain'):
    """Creates a domain 'mockdomain' and a web user with name/pw 
       'brian'/'test'.  Returns these two objects in a tuple 
       as (domain, user)"""
    try:
        domain = Domain.objects.get(name=domain_name)
        print "WARNING: tried to create domain %s but it already exists!" % domain_name
        print "Are all your tests cleaning up properly?"
    except Domain.DoesNotExist:
        # this is the normal case
        domain = Domain(name=domain_name, is_active=True)
        domain.save()
    
    try:
        user = User.objects.get(username=username)
        print "WARNING: tried to create user %s but it already exists!" % username
        print "Are all your tests cleaning up properly?"
        # update the pw anyway
        user.password = _get_salted_pw(password)
        user.save()
    except User.DoesNotExist:
        user = User()
        user.username = username
        # here, we mimic what the django auth system does
        # only we specify the salt to be 12345
        user.password = _get_salted_pw(password)
        
        user.save()
        
        # update the domain mapping using the Membership object
        mem = Membership()
        mem.domain = domain         
        mem.member_type = ContentType.objects.get_for_model(User)
        mem.member_id = user.id
        mem.is_active = True
        mem.save()
                
    return (user, domain)
                                
def create_reporter_with_connection(alias, 
                                    phone_number,
                                    backend):
    reporter = Reporter(alias=alias)
    reporter.save()
    conn, c_created = PersistantConnection.objects.get_or_create(\
                      identity=phone_number, backend=backend)
    conn.reporter = reporter
    conn.save()
    return reporter

def create_reporter_and_profile(backend, domain, phone_number="1234", username='username'):
    """Creates a domain 'mockdomain' and a sms user with name/pw 
       'brian'/'test'.  Returns these two objects in a tuple 
       as (domain, user)"""
    rep = create_reporter_with_connection(username, phone_number, backend)
    # note: we set reporterprofile.chw_username to be the same as username, just for testing
    prof = ReporterProfile(reporter=rep, domain=domain, chw_username=username)
    prof.save()
    return (rep, prof)

def create_active_reporter_and_profile(backend, domain, phone_number="1234", username='username'):
    rep, prof = create_reporter_and_profile(backend, domain, phone_number, username)
    prof.active = True
    prof.save()
    return (rep, prof)

def _get_salted_pw(password, salt="12345"):
    hashed_pass = hashlib.sha1(salt+password).hexdigest()
    return 'sha1$%s$%s' % (salt, hashed_pass)
        