# encoding: utf-8
from django.conf import settings
from django.core.management import call_command
import corehq.apps.sms.models as sms_models
from south.v2 import DataMigration
from dimagi.utils.couch import sync_docs
from corehq.apps.smsbillables.management.commands.bootstrap_grapevine_gateway import \
    bootstrap_grapevine_gateway
from corehq.apps.smsbillables.management.commands.bootstrap_mach_gateway import \
    bootstrap_mach_gateway
from corehq.apps.smsbillables.management.commands.bootstrap_tropo_gateway import \
    bootstrap_tropo_gateway
from corehq.apps.smsbillables.management.commands.bootstrap_twilio_gateway import \
    bootstrap_twilio_gateway
from corehq.apps.smsbillables.management.commands.bootstrap_unicel_gateway import \
    bootstrap_unicel_gateway


class Migration(DataMigration):

    def forwards(self, orm):
        # hack: manually force sync SMS design docs before
        # we try to load from them. the bootstrap commands are dependent on these.
        sync_docs.sync(sms_models, verbosity=2)

        # ensure default currency
        orm['accounting.Currency'].objects.get_or_create(code=settings.DEFAULT_CURRENCY)
        orm['accounting.Currency'].objects.get_or_create(code='EUR')
        orm['accounting.Currency'].objects.get_or_create(code='INR')

        bootstrap_grapevine_gateway(orm)
        bootstrap_mach_gateway(orm)
        bootstrap_tropo_gateway(orm)
        bootstrap_twilio_gateway(orm)
        bootstrap_unicel_gateway(orm)
        call_command('bootstrap_usage_fees')

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
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
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
