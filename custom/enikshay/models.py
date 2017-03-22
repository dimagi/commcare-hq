from django.db import models
from dimagi.ext.couchdbkit import Document, StringProperty, IntegerProperty
from corehq.util.decorators import serial_task


# option 1
# store a SQL model mapping user_id to pk (nikshay id)
# The nice thing about this approach is that django and postgres handle all the concurrency issues for us!
# also, this makes it easy to look up a user by nikshay id
# the downside is that it's a db row for every user.

class IssuerId(models.Model):
    """
    This model is used to ensure unique, incrementing issuer IDs for users,
    and to look up a user given an issuer ID.
    obj.pk represents the serial issuer ID, later representations will be added as fields
    """
    domain = models.CharField(max_length=255, db_index=True)
    user_id = models.CharField(max_length=50, db_index=True, unique=True)


def set_issuer_id_sql(domain, user):
    """Add a serially increasing custom user data "Issuer ID" to the user."""
    issuer_id, created = IssuerId.objects.get_or_create(domain=domain, user_id=user._id)
    user.user_data['issuer_id'] = issuer_id.pk
    user.save()


##############################################################
# option 2
# store a single document (per domain) in couch and keep the state there
# the nice thing about this is there's only one extra document rather than a ton
# the downside is that it doesn't help us look up users by id, and we have to
# handle the locking and retrying manually, which is marginally less reliable

class IssuerIdCounter(Document):
    domain = StringProperty()
    last_id = IntegerProperty()


def _get_or_create_counter(domain):
    key = [domain, 'IssuerIdCounter']
    existing = IssuerIdCounter.view(
        'by_domain_doc_type_date/view',
        startkey=key,
        endkey=key + [{}],
        reduce=False,
        include_docs=True,
    ).one()
    if existing:
        return existing
    return IssuerIdCounter(domain=domain, last_id=0)


@serial_task('{domain}', default_retry_delay=2, timeout=10, max_retries=10)
def set_issuer_id_couch(domain, user):
    counter = _get_or_create_counter(domain)
    issuer_id = counter.last_id + 1
    counter.last_id = issuer_id
    counter.save()
    user.user_data['issuer_id'] = issuer_id
    user.save()
