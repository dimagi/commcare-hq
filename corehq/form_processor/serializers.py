from rest_framework import serializers
from corehq.form_processor.models import CommCareCaseIndexSQL, CommCareCaseSQL

from .models import XFormInstanceSQL, XFormOperationSQL


class XFormOperationSQLSerializer(serializers.ModelSerializer):

    class Meta:
        model = XFormOperationSQL


class XFormInstanceSQLSerializer(serializers.ModelSerializer):
    history = XFormOperationSQLSerializer(many=True, read_only=True)
    form = serializers.JSONField(source='form_data')
    auth_context = serializers.DictField()
    openrosa_headers = serializers.DictField()

    class Meta:
        model = XFormInstanceSQL
        exclude = ('id',)


class CommCareCaseIndexSQLSerializer(serializers.ModelSerializer):

    class Meta:
        model = CommCareCaseIndexSQL


class CommCareCaseSQLSerializer(serializers.ModelSerializer):
    indices = CommCareCaseIndexSQLSerializer(many=True, read_only=True)

    class Meta:
        model = CommCareCaseSQL
