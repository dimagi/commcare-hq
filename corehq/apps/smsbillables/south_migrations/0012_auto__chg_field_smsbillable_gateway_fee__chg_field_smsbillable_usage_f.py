# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Changing field 'SmsBillable.gateway_fee'
        db.alter_column(u'smsbillables_smsbillable', 'gateway_fee_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['smsbillables.SmsGatewayFee'], null=True, on_delete=models.PROTECT))

        # Changing field 'SmsBillable.usage_fee'
        db.alter_column(u'smsbillables_smsbillable', 'usage_fee_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['smsbillables.SmsUsageFee'], null=True, on_delete=models.PROTECT))

        # Changing field 'SmsGatewayFee.currency'
        db.alter_column(u'smsbillables_smsgatewayfee', 'currency_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.Currency'], on_delete=models.PROTECT))

        # Changing field 'SmsGatewayFee.criteria'
        db.alter_column(u'smsbillables_smsgatewayfee', 'criteria_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['smsbillables.SmsGatewayFeeCriteria'], on_delete=models.PROTECT))

        # Changing field 'SmsGatewayFee.date_created'
        db.alter_column(u'smsbillables_smsgatewayfee', 'date_created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True))

        # Changing field 'SmsUsageFee.date_created'
        db.alter_column(u'smsbillables_smsusagefee', 'date_created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True))

        # Changing field 'SmsUsageFee.criteria'
        db.alter_column(u'smsbillables_smsusagefee', 'criteria_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['smsbillables.SmsUsageFeeCriteria'], on_delete=models.PROTECT))

    def backwards(self, orm):

        # Changing field 'SmsBillable.gateway_fee'
        db.alter_column(u'smsbillables_smsbillable', 'gateway_fee_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['smsbillables.SmsGatewayFee'], null=True))

        # Changing field 'SmsBillable.usage_fee'
        db.alter_column(u'smsbillables_smsbillable', 'usage_fee_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['smsbillables.SmsUsageFee'], null=True))

        # Changing field 'SmsGatewayFee.currency'
        db.alter_column(u'smsbillables_smsgatewayfee', 'currency_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.Currency']))

        # Changing field 'SmsGatewayFee.criteria'
        db.alter_column(u'smsbillables_smsgatewayfee', 'criteria_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['smsbillables.SmsGatewayFeeCriteria']))

        # Changing field 'SmsGatewayFee.date_created'
        db.alter_column(u'smsbillables_smsgatewayfee', 'date_created', self.gf('django.db.models.fields.DateField')(auto_now_add=True))

        # Changing field 'SmsUsageFee.date_created'
        db.alter_column(u'smsbillables_smsusagefee', 'date_created', self.gf('django.db.models.fields.DateField')(auto_now_add=True))

        # Changing field 'SmsUsageFee.criteria'
        db.alter_column(u'smsbillables_smsusagefee', 'criteria_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['smsbillables.SmsUsageFeeCriteria']))

    models = {
        u'accounting.currency': {
            'Meta': {'object_name': 'Currency'},
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '3'}),
            'date_updated': ('django.db.models.fields.DateField', [], {'auto_now': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_index': 'True'}),
            'rate_to_default': ('django.db.models.fields.DecimalField', [], {'default': "'1.0'", 'max_digits': '20', 'decimal_places': '9'}),
            'symbol': ('django.db.models.fields.CharField', [], {'max_length': '10'})
        },
        u'smsbillables.smsbillable': {
            'Meta': {'object_name': 'SmsBillable'},
            'api_response': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_sent': ('django.db.models.fields.DateField', [], {}),
            'direction': ('django.db.models.fields.CharField', [], {'max_length': '10', 'db_index': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_index': 'True'}),
            'gateway_fee': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['smsbillables.SmsGatewayFee']", 'null': 'True', 'on_delete': 'models.PROTECT'}),
            'gateway_fee_conversion_rate': ('django.db.models.fields.DecimalField', [], {'default': "'1.0'", 'null': 'True', 'max_digits': '20', 'decimal_places': '9'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_valid': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'}),
            'log_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'}),
            'phone_number': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'usage_fee': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['smsbillables.SmsUsageFee']", 'null': 'True', 'on_delete': 'models.PROTECT'})
        },
        u'smsbillables.smsgatewayfee': {
            'Meta': {'object_name': 'SmsGatewayFee'},
            'amount': ('django.db.models.fields.DecimalField', [], {'default': '0.0', 'max_digits': '10', 'decimal_places': '4'}),
            'criteria': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['smsbillables.SmsGatewayFeeCriteria']", 'on_delete': 'models.PROTECT'}),
            'currency': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Currency']", 'on_delete': 'models.PROTECT'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'smsbillables.smsgatewayfeecriteria': {
            'Meta': {'object_name': 'SmsGatewayFeeCriteria'},
            'backend_api_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'backend_instance': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'country_code': ('django.db.models.fields.IntegerField', [], {'db_index': 'True', 'max_length': '5', 'null': 'True', 'blank': 'True'}),
            'direction': ('django.db.models.fields.CharField', [], {'max_length': '10', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'prefix': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '10', 'db_index': 'True', 'blank': 'True'})
        },
        u'smsbillables.smsusagefee': {
            'Meta': {'object_name': 'SmsUsageFee'},
            'amount': ('django.db.models.fields.DecimalField', [], {'default': '0.0', 'max_digits': '10', 'decimal_places': '4'}),
            'criteria': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['smsbillables.SmsUsageFeeCriteria']", 'on_delete': 'models.PROTECT'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'smsbillables.smsusagefeecriteria': {
            'Meta': {'object_name': 'SmsUsageFeeCriteria'},
            'direction': ('django.db.models.fields.CharField', [], {'max_length': '10', 'db_index': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '25', 'null': 'True', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        }
    }

    complete_apps = ['smsbillables']