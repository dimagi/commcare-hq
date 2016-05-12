from rest_framework import serializers

from corehq.apps.commtrack.models import StockState
from corehq.form_processor.models import (
    CommCareCaseIndexSQL, CommCareCaseSQL, CaseTransaction,
    XFormInstanceSQL, XFormOperationSQL,
    LedgerValue)


def get_instance_from_data(SerializerClass, data):
    """
    Return a deserialized instance from serialized data

    cf. https://github.com/tomchristie/django-rest-framework/blob/master/rest_framework/serializers.py#L71
    and https://github.com/tomchristie/django-rest-framework/blob/master/rest_framework/serializers.py#L882
    """
    # It does seem like you should be able to do this in one line. Django REST framework makes the assumption that
    # you always want to save(). This function does everything ModelSerializer.save() does, just without saving.
    ModelClass = SerializerClass.Meta.model
    serializer = SerializerClass(data=data)
    if not serializer.is_valid():
        raise ValueError('Unable to deserialize data while creating {}: {}'.format(ModelClass, serializer.errors))
    return ModelClass(**serializer.validated_data)


class DeletableModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional `fields` argument that
    controls which fields should be displayed.
    """

    def __init__(self, instance=None, *args, **kwargs):
        super(DeletableModelSerializer, self).__init__(instance=instance, *args, **kwargs)
        if instance is not None and not instance.is_deleted:
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
    date = serializers.DateTimeField(source='server_date')

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


class CommCareCaseSQLAPISerializer(serializers.ModelSerializer):
    """This serializer is for presenting a case in json for APIs to access"""
    user_id = serializers.CharField(source='modified_by')
    date_closed = serializers.DateTimeField(source='closed_on')
    date_modified = serializers.DateTimeField(source='modified_on')
    properties = serializers.JSONField(source='get_properties_in_api_format')
    server_date_modified = serializers.DateTimeField(source='server_modified_on')
    server_date_opened = serializers.DateTimeField(source='opened_on')
    indices = serializers.JSONField(source='get_index_map')
    attachments = serializers.JSONField(source='get_attachment_map')
    reverse_indices = serializers.JSONField(source='get_reverse_index_map')

    def __init__(self, *args, **kwargs):
        lite = kwargs.pop('lite', False)
        if lite:
            self.fields.pop('reverse_indices')
        super(CommCareCaseSQLAPISerializer, self).__init__(*args, **kwargs)

    class Meta:
        model = CommCareCaseSQL
        fields = (
            'domain',
            'case_id',
            'user_id',
            'closed',
            'xform_ids',
            'date_closed',
            'date_modified',
            'server_date_modified',
            'server_date_opened',
            'properties',
            'indices',
            'reverse_indices',
            'attachments',
        )


class LedgerValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerValue
        exclude = ('id',)


class StockStateSerializer(serializers.ModelSerializer):
    _id = serializers.IntegerField(source='id')
    entry_id = serializers.CharField(source='product_id')
    location_id = serializers.CharField(source='sql_location.location_id')
    balance = serializers.CharField(source='stock_on_hand')
    last_modified = serializers.CharField(source='last_modified_date')

    class Meta:
        model = StockState
        exclude = (
            'id',
            'product_id',
            'stock_on_hand',
            'last_modified_date',
            'sql_product',
            'sql_location',
        )
