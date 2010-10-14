from django.db import models
from couchdbkit.ext.django.schema import Document
from couchdbkit.schema.properties import StringProperty, DictProperty
from corehq.apps.domain.models import Domain
from django.core.urlresolvers import reverse

class RemoteApp(Document):
    domain = StringProperty()
    url = StringProperty()
    name = DictProperty()

    @classmethod
    def get_app(cls, domain, app_id):
        # raise error if domain doesn't exist
        Domain.objects.get(name=domain)
        app = RemoteApp.get(app_id)
        if app.domain != domain:
            raise Exception("App %s not in domain %s" % (app_id, domain))
        return app

    @property
    def id(self):
        return self._id

    def get_absolute_url(self):
        return reverse('corehq.apps.remote_apps.views.app_view', args=[self.domain, self.id])