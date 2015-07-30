# encoding: utf-8
import datetime
from django.core.management import call_command
from south.db import db
from south.v2 import DataMigration
from django.db import models

class Migration(DataMigration):

    def forwards(self, orm):
        call_command('bootstrap_test_gateway')
        call_command('bootstrap_telerivet_gateway')


    def backwards(self, orm):
        pass


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
            'gateway_fee': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['smsbillables.SmsGatewayFee']", 'null': 'True'}),
            'gateway_fee_conversion_rate': ('django.db.models.fields.DecimalField', [], {'default': "'1.0'", 'null': 'True', 'max_digits': '20', 'decimal_places': '9'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_valid': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'}),
            'log_id': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'phone_number': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'usage_fee': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['smsbillables.SmsUsageFee']", 'null': 'True'})
        },
        u'smsbillables.smsgatewayfee': {
            'Meta': {'object_name': 'SmsGatewayFee'},
            'amount': ('django.db.models.fields.DecimalField', [], {'default': '0.0', 'max_digits': '10', 'decimal_places': '4'}),
            'criteria': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['smsbillables.SmsGatewayFeeCriteria']"}),
            'currency': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Currency']"}),
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
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
            'criteria': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['smsbillables.SmsUsageFeeCriteria']"}),
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
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
