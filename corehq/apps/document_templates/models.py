from attrs import define, field
from django.db import models
from django.utils.translation import gettext_lazy

from corehq.util.jsonattrs import AttrsDict


class AreaType(models.TextChoices):
    MARKDOWN = 'markdown', gettext_lazy('Markdown')
    IMAGE = 'image', gettext_lazy('Image')


@define
class Area:
    value = field(default='')
    type = field(default=AreaType.MARKDOWN)


class Template(models.Model):
    domain = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=50)
    areas = AttrsDict(Area)
    deleted = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['domain', 'slug'],
                condition=models.Q(deleted=False),
                name='document_templates_template_domain_slug',
            ),
        ]

    def __str__(self):
        return self.name
