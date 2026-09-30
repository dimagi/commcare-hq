from django.db import models


class LetterTemplate(models.Model):
    """
    Domain-authored Jinja2 HTML template, rendered against a case's
    properties by the Letters report. Case-type agnostic and unversioned:
    rendering always uses the current body.
    """
    domain = models.CharField(max_length=126, db_index=True)
    name = models.CharField(max_length=255)
    body = models.TextField()
    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
