from django.db import models
from django.db.models.fields import CharField, DateField

from django.contrib.auth.models import User


class GoogleApiToken(models.Model):
    user = models.ForeignKey(User, related_name='google_api_tokens', on_delete=models.CASCADE)
    token = CharField(max_length=700)
    date_created = DateField(auto_now_add=True)
