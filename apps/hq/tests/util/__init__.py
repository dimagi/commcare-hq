"""We put utility code in a separate package so that other tests 
   can use it without triggering this app's unit tests 
"""

from hq.models import ExtUser, Domain

def create_user_and_domain():
    """Creates a domain 'mockdomain' and a user with name/pw 
       'brian'/'test'.  Returns these two objects in a tuple 
       as (domain, user)"""
    domain = Domain(name='mockdomain')
    domain.save()
    user = ExtUser()
    user.domain = domain
    user.username = 'brian'
    user.password = 'sha1$245de$137d06d752eee1885a6bbd1e40cbe9150043dd5e'
    user.save()
    return (user, domain)