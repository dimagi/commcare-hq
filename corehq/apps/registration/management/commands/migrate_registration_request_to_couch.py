import datetime
from django.conf import settings
from django.core.management.base import LabelCommand

# OldRegistrationRequest no longer exists. Should this command be removed?
#from corehq.apps.registration.models import OldRegistrationRequest, RegistrationRequest

class Command(LabelCommand):
    help = "Migrates old django RegistrationRequest model to new couch model. March 2012."
    args = ""
    label = ""

    def handle(self, *args, **options):
        django_requests = OldRegistrationRequest.objects.all()

        print "Migrating RegistrationRequest Model from django to couch"

        for request in django_requests:
            existing_request = None
            try:
                existing_request = RegistrationRequest.get_by_guid(request.activation_guid)
            except Exception:
                pass
            try:
                if not existing_request:
                    new_req = RegistrationRequest(tos_confirmed=request.tos_confirmed,
                        request_time=request.request_time,
                        request_ip=request.request_ip,
                        activation_guid=request.activation_guid,
                        confirm_time=request.confirm_time,
                        confirm_ip=request.confirm_ip,
                        domain=request.domain.name,
                        new_user_username=request.new_user.username,
                        requesting_user_username=request.requesting_user.username)
                    new_req.save()
            except Exception as e:
                print "There was an error migrating a registration request with guid %s." % request.activation_guid
                print "Error: %s" % e