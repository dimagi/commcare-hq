"""We put utility code in a separate package so that other tests 
   can use it without triggering this app's unit tests 
"""

import hashlib
from hq.models import ExtUser, Domain

def create_user_and_domain(username='brian', 
                           password='test',
                           domain_name='mockdomain'):
    """Creates a domain 'mockdomain' and a user with name/pw 
       'brian'/'test'.  Returns these two objects in a tuple 
       as (domain, user)"""
    domain = Domain(name=domain_name)
    domain.save()
    user = ExtUser()
    user.domain = domain
    user.username = username
    # here, we mimic what the django auth system does
    # only we specify the salt to be 12345
    salt = '12345'
    hashed_pass = hashlib.sha1(salt+password).hexdigest()
    user.password = 'sha1$%s$%s' % (salt, hashed_pass)
    
    user.set_unsalted_password( username, password )
    user.save()
    return (user, domain)
