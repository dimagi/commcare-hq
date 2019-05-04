from __future__ import absolute_import
from __future__ import unicode_literals

from rest_framework import serializers

from custom.icds.models import (
    CCZHosting,
    CCZHostingLink,
)


class CCZHostingLinkSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = CCZHostingLink
        fields = ['identifier', 'username', 'id', 'page_title']


class CCZHostingSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = CCZHosting
        fields = ['id', 'link', 'app_id', 'version']

    def to_representation(self, instance):
        ret = super(CCZHostingSerializer, self).to_representation(instance)
        ret['app_name'] = self.context['app_names'][ret['app_id']]
        ret['link_name'] = self.instance.link.identifier
        ret['profile_name'] = self.instance.build_profile['name']
        ret['file_name'] = self.instance.file_name
        if self.instance.blob_id:
            ret['ccz_details'] = self.instance.utility.ccz_details
        return ret
