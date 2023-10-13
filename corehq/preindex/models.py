from couchdbkit.ext.django import syncdb
from django.db.models import signals


signals.post_migrate.disconnect(syncdb)
