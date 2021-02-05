import uuid
from datetime import datetime

from django.db import models
from jsonfield import JSONField


class AuthenticatedLink(models.Model):
    link_id = models.UUIDField(unique=True, db_index=True, default=uuid.uuid4)
    domain = models.CharField(max_length=126, null=False, db_index=True)
    data = JSONField(blank=True, null=True)
    created_on = models.DateTimeField(auto_now=True)
    expires_on = models.DateTimeField(null=True, blank=True)
    is_visited = models.BooleanField(default=False)
    visited_on = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)
    used_on = models.DateTimeField(null=True, blank=True)

    def is_valid(self):
        return not self.is_used and self.expires_on is None or self.expires_on > datetime.utcnow()
