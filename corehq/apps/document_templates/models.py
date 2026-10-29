from django.db import models


class Template(models.Model):
    domain = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=50)
    variables = models.JSONField()
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
