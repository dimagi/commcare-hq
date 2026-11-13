from attrs import define, field
from django.db import models

from corehq.util.jsonattrs import AttrsDict


MARKDOWN = 'markdown'
IMAGE = 'image'
AREA_TYPES = (MARKDOWN, IMAGE)


@define
class Area:
    value = field(default='')
    type = field(default=MARKDOWN)


class Template(models.Model):
    domain = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=50)
    areas = AttrsDict(Area)
    deleted = models.BooleanField(default=False)
    upstream_id = models.IntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['domain', 'slug'],
                condition=models.Q(deleted=False),
                name='document_templates_template_domain_slug',
            ),
            models.UniqueConstraint(
                fields=['domain', 'upstream_id'],
                name='document_templates_template_domain_upstream_id',
            ),
        ]

    def __str__(self):
        return self.name
