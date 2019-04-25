from __future__ import absolute_import
from __future__ import unicode_literals

from rest_framework import serializers

from custom.icds.models import (
    CCZHostingLink,
)


class CCZHostingLinkSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = CCZHostingLink
        fields = ['identifier', 'username', 'id']
