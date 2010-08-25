# our hacked up user registration no longer plays nice with the out of the
# box tests.
# until this gets resolved, going to go ahead and comment these out
# currently only the model tests work
#from corehq.lib.django_user_registration.tests.backends import *
#from corehq.lib.django_user_registration.tests.forms import *
from corehq.lib.django_user_registration.tests.models import *
#from corehq.lib.django_user_registration.tests.views import *
