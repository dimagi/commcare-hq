import jsonfield
from django.db import models
from django.db import transaction

from corehq.apps.email.util import BadEmailConfigException, get_email_backend_classes
from corehq.util.quickcache import quickcache


class EmailSMTPBackend(models.Model):
    objects = models.Manager()

    # This tells us which type of backend this is
    hq_api_id = models.CharField(max_length=126, null=True)

    # This is the domain that the backend belongs to
    domain = models.CharField(max_length=126, null=True, db_index=True)

    # Name of the backend - e.g. "aws"
    name = models.CharField(max_length=126, null=True)

    # Simple name to display to users - e.g. "AWS"
    display_name = models.CharField(max_length=126, null=True)

    # Optionally, a description of this backend
    description = models.TextField(null=True)

    username = models.CharField(max_length=100)

    password = models.CharField(max_length=150)

    server = models.CharField(max_length=50)

    port = models.CharField(max_length=5)

    extra_fields = jsonfield.JSONField(default=dict)

    is_default = models.BooleanField(default=False)

    class Meta(object):
        db_table = 'messaging_emailbackend'
        app_label = 'email'

    def __str__(self):
        return "Domain '%s' Backend '%s'" % (self.domain, self.name)

    def domain_is_authorized(self, domain):
        """
        Returns True if the given domain is authorized to use this backend.
        """
        return domain == self.domain

    @classmethod
    def name_is_unique(cls, name, domain, backend_id):
        result = cls.objects.filter(
            domain=domain,
            name=name,
        )

        result = result.values_list('id', flat=True)
        if len(result) == 0:
            return True

        if len(result) == 1:
            return result[0] == backend_id

        return False

    @classmethod
    def get_domain_backends(cls, domain, count_only=False, offset=None, limit=None):
        """
        Returns all the backends that the given domain has access to.
        """
        domain_owned_backends = models.Q(domain=domain)
        result = EmailSMTPBackend.objects.filter(domain_owned_backends).distinct()

        if count_only:
            return result.count()

        result = result.order_by('name').values_list('id', flat=True)

        if offset is not None and limit is not None:
            result = result[offset:offset + limit]

        return [cls.load(pk) for pk in result]

    @classmethod
    def get_domain_default_backend(cls, domain):
        result = EmailSMTPBackend.objects.filter(
            domain=domain,
            is_default=True,
        ).values_list(flat=True)

        if len(result) > 1:
            raise cls.MultipleObjectsReturned(
                "More than one default backend found for "
                "domain %s" % (domain)
            )
        elif len(result) == 1:
            return cls.load(result[0])
        return None

    @staticmethod
    @transaction.atomic
    def set_to_domain_default_backend(existing_default_backend, current_backend):
        if existing_default_backend and current_backend:
            EmailSMTPBackend._make_backend_non_default(existing_default_backend)

        current_backend.is_default = True
        current_backend.save()

    @staticmethod
    def unset_domain_default_backend(existing_default_backend):
        if existing_default_backend:
            EmailSMTPBackend._make_backend_non_default(existing_default_backend)

    @staticmethod
    def _make_backend_non_default(backend):
        backend.is_default = False
        backend.save()

    @classmethod
    @quickcache(['backend_id'], timeout=60 * 60)
    def get_backend_api_id(cls, backend_id):
        filter_args = {'pk': backend_id}
        result = EmailSMTPBackend.objects.filter(**filter_args).values_list('hq_api_id', flat=True)

        if len(result) == 0:
            raise cls.DoesNotExist

        return result[0]

    @classmethod
    @quickcache(['backend_id'], timeout=5 * 60)
    def load(cls, backend_id, api_id=None):
        """
        backend_id - the pk of the SQLEmailSMTPBackend to load
        api_id - if you know the hq_api_id of the SQLEmailSNTPBackend, pass it
                 here for a faster lookup; otherwise, it will be looked up
                 automatically
        """
        backend_classes = get_email_backend_classes()
        api_id = api_id or cls.get_backend_api_id(backend_id)

        if api_id not in backend_classes:
            raise BadEmailConfigException("Unexpected backend api id found '%s' for "
                                          "backend '%s'" % (api_id, backend_id))

        klass = backend_classes[api_id]
        result = klass.objects
        return result.get(pk=backend_id)
