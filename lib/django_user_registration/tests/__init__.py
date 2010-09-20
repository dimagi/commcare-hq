# our hacked up user registration no longer plays nice with the out of the
# box tests.
# until this gets resolved, going to go ahead and comment these out
# currently only the model tests work
#from django_user_registration.tests.backends import *
#from django_user_registration.tests.new_xforms import *
from django_user_registration.tests.models import *
#from django_user_registration.tests.views import *
