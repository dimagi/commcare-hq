from http import HTTPMethod

from attrs import define, field
from django.db import models

from corehq.util.jsonattrs import AttrsList


@define
class AllowedEndpoint:
    method: HTTPMethod = field(converter=HTTPMethod)
    path: str = field()


class SidecarApp(models.Model):
    domain = models.CharField(max_length=126, db_index=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    created_on = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    url = models.URLField()
    api_allowlist = AttrsList(
        AllowedEndpoint,
        default=list,
        blank=True,
        help_text='List of {"method": "GET", "path": "/api/case/v2/"} entries. '
                  'Paths are prefixes, relative to the project.',
    )

    class Meta:
        unique_together = ('domain', 'slug')
