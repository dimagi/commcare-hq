import copy
from datetime import datetime
from couchdbkit.exceptions import ResourceNotFound
from couchdbkit.ext.django.schema import *
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import render

class PrescriptionDateOutOfRange(Exception):
    pass
class PrescriptionUnauthorized(Exception):
    pass

class Prescription(Document):
    domain = StringProperty()
    user_ids = StringListProperty()
    all_admin = BooleanProperty(default=True)
    type = StringProperty()
    start = DateTimeProperty()
    end = DateTimeProperty()
    params = DictProperty()

    def check(self, type, domain, user, now=None):
        now = now or datetime.utcnow()
        if not (self.type == type and self.domain == domain):
            raise PrescriptionUnauthorized()

        if not user.is_superuser:
            if not self.start < now < self.end:
                raise PrescriptionDateOutOfRange()

            if not (
                user.user_id in self.user_ids or
                (self.all_admin and user.is_domain_admin())
            ):
                raise PrescriptionUnauthorized()


    @classmethod
    def all(cls):
        return cls.view('prescriptions/all', include_docs=True)

    @classmethod
    def require(cls, type):
        """
        Decorator for views that are be prescription-only
        
        Does the courtesy of passing in a prescription object (rather than just the id) and
        all the prescriptions params to the view as keyword arguments

        """
        def decorator(fn):
            def new_fn(request, domain, prescription_id, *args, **kwargs):
                try:
                    prescription = Prescription.get(prescription_id)
                except ResourceNotFound:
                    raise Http404()
                now = datetime.utcnow()
                try:
                    prescription.check(type, domain, request.couch_user, now=now)
                except PrescriptionUnauthorized:
                    return HttpResponseForbidden()
                except PrescriptionDateOutOfRange:
                    return render(request, 'prescriptions/date_out_of_range.html', {
                        'now': now,
                        'prescription': prescription,
                    })
                else:
                    return fn(request, domain, prescription, *args, **kwargs)

            return new_fn
        return decorator
