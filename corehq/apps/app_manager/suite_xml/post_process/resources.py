from django.db import models

from corehq.apps.app_manager.suite_xml.contributors import PostProcessor


class ResourceOverride(models.Model):
    domain = models.CharField(max_length=255, null=False)
    app_id = models.CharField(max_length=255, null=False)
    root_name = models.CharField(max_length=32, null=False) # matches up with class in suite_xml.xml_models
    pre_id = models.CharField(max_length=255, null=False)
    post_id = models.CharField(max_length=255, null=False)


class ResourceOverrideHelper(PostProcessor):

    def update_suite(self):
        pass
