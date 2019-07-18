from __future__ import absolute_import
from __future__ import unicode_literals

from rest_framework import serializers

from custom.icds.models import (
    HostedCCZ,
    HostedCCZLink,
)


class HostedCCZLinkSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = HostedCCZLink
        fields = ['identifier', 'username', 'id', 'page_title']


class HostedCCZSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = HostedCCZ
        fields = ['id', 'link', 'app_id', 'version', 'note']

    def to_representation(self, instance):
        ret = super(HostedCCZSerializer, self).to_representation(instance)
        ret['app_name'] = self.context['app_names'][ret['app_id']]
        ret['link_name'] = self.instance.link.identifier
        ret['profile_name'] = self.instance.build_profile['name'] if self.instance.profile_id else ''
        ret['file_name'] = self.instance.file_name
        if self.instance.blob_id:
            ret['ccz_details'] = self.instance.utility.ccz_details
        return ret
