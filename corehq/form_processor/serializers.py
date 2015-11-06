from rest_framework import serializers

from .models import XFormInstanceSQL, XFormOperationSQL


class XFormOperationSQLSerializer(serializers.ModelSerializer):

    class Meta:
        model = XFormOperationSQL


class XFormInstanceSQLSerializer(serializers.ModelSerializer):
    history = XFormOperationSQLSerializer(many=True, read_only=True)
    form = serializers.JSONField(source='form_data')

    class Meta:
        model = XFormInstanceSQL
