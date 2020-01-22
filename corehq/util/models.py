from django.db import models


class BouncedEmail(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    email = models.EmailField(db_index=True, unique=True)
