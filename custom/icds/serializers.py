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
        fields = ['id', 'link', 'app_id', 'version', 'note', 'status']

    def to_representation(self, instance):
        ret = super(HostedCCZSerializer, self).to_representation(instance)
        if instance.build_doc:
            ret['app_name'] = instance.build_doc.get('name')
            custom_properties = instance.build_doc.get('profile', {}).get('custom_properties', {})
            ret['app_version_tag'] = custom_properties.get('cc-app-version-tag')
        ret['link_name'] = self.instance.link.identifier
        ret['profile_name'] = self.instance.build_profile['name'] if self.instance.profile_id else ''
        ret['file_name'] = self.instance.file_name
        if self.instance.blob_id:
            ret['ccz_details'] = self.instance.utility.ccz_details
        return ret
