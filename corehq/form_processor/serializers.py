from rest_framework import serializers
from corehq.form_processor.models import (
    CommCareCaseIndexSQL, CommCareCaseSQL, CaseTransaction,
    XFormInstanceSQL, XFormOperationSQL
)


class DeletableModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional `fields` argument that
    controls which fields should be displayed.
    """

    def __init__(self, instance=None, *args, **kwargs):
        super(DeletableModelSerializer, self).__init__(instance=instance, *args, **kwargs)
        if not instance.is_deleted:
            self.fields.pop('deletion_id')
            self.fields.pop('deleted_on')


class XFormOperationSQLSerializer(serializers.ModelSerializer):

    class Meta:
        model = XFormOperationSQL


class XFormInstanceSQLSerializer(DeletableModelSerializer):
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


class CaseTransactionActionSerializer(serializers.ModelSerializer):
    xform_id = serializers.CharField(source='form_id')
    date = serializers.CharField(source='server_date')

    class Meta:
        model = CaseTransaction
        fields = ('xform_id', 'server_date', 'date', 'sync_log_id')


class CommCareCaseSQLSerializer(DeletableModelSerializer):
    _id = serializers.CharField(source='case_id')
    doc_type = serializers.CharField()
    user_id = serializers.CharField(source='modified_by')
    indices = CommCareCaseIndexSQLSerializer(many=True, read_only=True)
    actions = CaseTransactionActionSerializer(many=True, read_only=True, source='non_revoked_transactions')
    case_json = serializers.JSONField()

    class Meta:
        model = CommCareCaseSQL
        exclude = ('case_json',)
