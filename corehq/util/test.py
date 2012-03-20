import hashlib
from corehq.apps.domain.models import Domain
from django.contrib.auth.models import User
import tempfile

def create_user_and_domain(username='brian', 
                           password='test',
                           domain_name='mockdomain'):
    """Creates a domain 'mockdomain' and a web user with name/pw 
       'brian'/'test'.  Returns these two objects in a tuple 
       as (domain, user).  The parameters are configurable."""
    try:
        domain = Domain.get_by_name(domain_name)
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
        
    return (user, domain)

def replace_in_file(filename, to_replace, replace_with):
    """
    Replace some stuff in a file with some other stuff,
    returning a handle to the new file.  Useful for testing
    mostly-similar xforms with small changes.
    """   
    xml_data = open(filename, "rb").read()  
    xml_data = xml_data.replace(to_replace, replace_with)
    tmp_file_path = tempfile.TemporaryFile().name
    tmp_file = open(tmp_file_path, "w")
    tmp_file.write(xml_data)
    tmp_file.close()
    return tmp_file_path
    
                            
def _get_salted_pw(password, salt="12345"):
    hashed_pass = hashlib.sha1(salt+password).hexdigest()
    return 'sha1$%s$%s' % (salt, hashed_pass)
        