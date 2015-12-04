from django.db import models
import json_field


class GuidedTours(models.Model):
    web_user = models.CharField(max_length=80, null=False)
    tours = json_field.JSONField(
        default={},
    )
    history = json_field.JSONField(
        default={},
    )

    @classmethod
    def enable_tour_for_user(cls, tour_slug, web_user):
        # todo
        pass

    @classmethod
    def is_tour_enabled_for_user(cls, tour_slug, web_user):
        # todo
        return True
