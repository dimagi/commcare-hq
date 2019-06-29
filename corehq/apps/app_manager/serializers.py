from __future__ import absolute_import
from __future__ import unicode_literals

from rest_framework import serializers

from corehq.apps.app_manager.models import (
    LatestEnabledBuildProfiles,
)


class LatestEnabledBuildProfileSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = LatestEnabledBuildProfiles

    def to_representation(self, instance):
        ret = super(LatestEnabledBuildProfileSerializer, self).to_representation(instance)
        return ret
