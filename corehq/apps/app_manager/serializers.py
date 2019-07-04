from __future__ import absolute_import
from __future__ import unicode_literals

from rest_framework import serializers

from corehq.apps.app_manager.models import (
    LatestEnabledBuildProfiles,
)


class LatestEnabledBuildProfileSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = LatestEnabledBuildProfiles
        fields = ['id', 'app_id', 'active', 'version']

    def to_representation(self, instance):
        ret = super(LatestEnabledBuildProfileSerializer, self).to_representation(instance)
        build_profile_id = self.instance.build_profile_id
        ret['app_name'] = self.context['app_names'][ret['app_id']]
        ret['profile_name'] = self.instance.build.build_profiles[build_profile_id].name
        return ret
