from django.db import models


class DialerSettings(models.Model):
    domain = models.CharField(max_length=128, unique=True)
    aws_instance_id = models.CharField(max_length=255)
    is_enabled = models.BooleanField(default=False)
    dialer_page_header = models.CharField(max_length=255)
    dialer_page_subheader = models.CharField(max_length=255)
