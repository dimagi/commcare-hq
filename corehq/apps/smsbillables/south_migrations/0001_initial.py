# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    depends_on = (
        ("accounting", "0001_initial"),
    )

    def forwards(self, orm):
        
        # Adding model 'SmsGatewayFeeCriteria'
        db.create_table('smsbillables_smsgatewayfeecriteria', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('backend_api_id', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('backend_instance', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, db_index=True)),
            ('direction', self.gf('django.db.models.fields.CharField')(max_length=10, db_index=True)),
            ('country_code', self.gf('django.db.models.fields.IntegerField')(db_index=True, max_length=5, null=True, blank=True)),
        ))
        db.send_create_signal('smsbillables', ['SmsGatewayFeeCriteria'])

        # Adding model 'SmsGatewayFee'
        db.create_table('smsbillables_smsgatewayfee', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('criteria', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['smsbillables.SmsGatewayFeeCriteria'])),
            ('amount', self.gf('django.db.models.fields.DecimalField')(default=0.0, max_digits=10, decimal_places=4)),
            ('currency', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.Currency'])),
            ('date_created', self.gf('django.db.models.fields.DateField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal('smsbillables', ['SmsGatewayFee'])

        # Adding model 'SmsUsageFeeCriteria'
        db.create_table('smsbillables_smsusagefeecriteria', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('direction', self.gf('django.db.models.fields.CharField')(max_length=10, db_index=True)),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=25, null=True, db_index=True)),
        ))
        db.send_create_signal('smsbillables', ['SmsUsageFeeCriteria'])

        # Adding model 'SmsUsageFee'
        db.create_table('smsbillables_smsusagefee', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('criteria', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['smsbillables.SmsUsageFeeCriteria'])),
            ('amount', self.gf('django.db.models.fields.DecimalField')(default=0.0, max_digits=10, decimal_places=4)),
            ('date_created', self.gf('django.db.models.fields.DateField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal('smsbillables', ['SmsUsageFee'])

        # Adding model 'SmsBillable'
        db.create_table('smsbillables_smsbillable', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('gateway_fee', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['smsbillables.SmsGatewayFee'], null=True)),
            ('gateway_fee_conversion_rate', self.gf('django.db.models.fields.DecimalField')(default=1.0, null=True, max_digits=20, decimal_places=9)),
            ('usage_fee', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['smsbillables.SmsUsageFee'], null=True)),
            ('log_id', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('phone_number', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('api_response', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('is_valid', self.gf('django.db.models.fields.BooleanField')(default=True, db_index=True)),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=25, db_index=True)),
            ('direction', self.gf('django.db.models.fields.CharField')(max_length=10, db_index=True)),
            ('date_sent', self.gf('django.db.models.fields.DateField')()),
            ('date_created', self.gf('django.db.models.fields.DateField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal('smsbillables', ['SmsBillable'])


    def backwards(self, orm):
        
        # Deleting model 'SmsGatewayFeeCriteria'
        db.delete_table('smsbillables_smsgatewayfeecriteria')

        # Deleting model 'SmsGatewayFee'
        db.delete_table('smsbillables_smsgatewayfee')

        # Deleting model 'SmsUsageFeeCriteria'
        db.delete_table('smsbillables_smsusagefeecriteria')

        # Deleting model 'SmsUsageFee'
        db.delete_table('smsbillables_smsusagefee')

        # Deleting model 'SmsBillable'
        db.delete_table('smsbillables_smsbillable')


    models = {
        'accounting.currency': {
            'Meta': {'object_name': 'Currency'},
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '3'}),
            'date_updated': ('django.db.models.fields.DateField', [], {'auto_now': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_index': 'True'}),
            'rate_to_default': ('django.db.models.fields.DecimalField', [], {'default': '1.0', 'max_digits': '20', 'decimal_places': '9'}),
            'symbol': ('django.db.models.fields.CharField', [], {'max_length': '10'})
        },
        'smsbillables.smsbillable': {
            'Meta': {'object_name': 'SmsBillable'},
            'api_response': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_sent': ('django.db.models.fields.DateField', [], {}),
            'direction': ('django.db.models.fields.CharField', [], {'max_length': '10', 'db_index': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_index': 'True'}),
            'gateway_fee': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['smsbillables.SmsGatewayFee']", 'null': 'True'}),
            'gateway_fee_conversion_rate': ('django.db.models.fields.DecimalField', [], {'default': '1.0', 'null': 'True', 'max_digits': '20', 'decimal_places': '9'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_valid': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'}),
            'log_id': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'phone_number': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'usage_fee': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['smsbillables.SmsUsageFee']", 'null': 'True'})
        },
        'smsbillables.smsgatewayfee': {
            'Meta': {'object_name': 'SmsGatewayFee'},
            'amount': ('django.db.models.fields.DecimalField', [], {'default': '0.0', 'max_digits': '10', 'decimal_places': '4'}),
            'criteria': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['smsbillables.SmsGatewayFeeCriteria']"}),
            'currency': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['accounting.Currency']"}),
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'smsbillables.smsgatewayfeecriteria': {
            'Meta': {'object_name': 'SmsGatewayFeeCriteria'},
            'backend_api_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'backend_instance': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'country_code': ('django.db.models.fields.IntegerField', [], {'db_index': 'True', 'max_length': '5', 'null': 'True', 'blank': 'True'}),
            'direction': ('django.db.models.fields.CharField', [], {'max_length': '10', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'smsbillables.smsusagefee': {
            'Meta': {'object_name': 'SmsUsageFee'},
            'amount': ('django.db.models.fields.DecimalField', [], {'default': '0.0', 'max_digits': '10', 'decimal_places': '4'}),
            'criteria': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['smsbillables.SmsUsageFeeCriteria']"}),
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'smsbillables.smsusagefeecriteria': {
            'Meta': {'object_name': 'SmsUsageFeeCriteria'},
            'direction': ('django.db.models.fields.CharField', [], {'max_length': '10', 'db_index': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '25', 'null': 'True', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        }
    }

    complete_apps = ['smsbillables']
