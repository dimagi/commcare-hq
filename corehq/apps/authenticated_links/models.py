import uuid
from datetime import datetime

from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


class AuthenticatedLink(models.Model):
    link_id = models.UUIDField(unique=True, db_index=True, default=uuid.uuid4)
    domain = models.CharField(max_length=126, null=False, db_index=True)
    created_on = models.DateTimeField(auto_now=True)
    expires_on = models.DateTimeField(null=True, blank=True)
    allows_submission = models.BooleanField(default=False, help_text=_('If the link allows data submission'))
    submitting_user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        help_text=_('For links that allow data submission, the user to be used to submit data.'),
    )
    is_visited = models.BooleanField(default=False)
    visited_on = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)
    used_on = models.DateTimeField(null=True, blank=True)

    def is_valid(self):
        return not self.is_used and self.expires_on is None or self.expires_on > datetime.utcnow()

    @property
    def case_ids(self):
        # most of HQ that uses case ids expects them to be a list of of strings and not a
        # queryset of uuids...
        return [str(case_id) for case_id in self.case_data.values_list('case_id', flat=True)]

    def get_url(self):
        return reverse('authenticated_links:access_authenticated_link', args=[self.domain, self.link_id])

    def get_data(self):
        return [
            c.to_json() for c in CaseAccessors(self.domain).get_cases(self.case_ids)
        ]


class CaseReference(models.Model):

    link = models.ForeignKey(AuthenticatedLink, on_delete=models.CASCADE, related_name='case_data')
    case_id = models.UUIDField()
    # in the future could also attach metadata

    class Meta:
        unique_together = ('link', 'case_id')

