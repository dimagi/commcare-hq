# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'Invoice.last_modified'
        db.add_column(u'accounting_invoice', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 504287), auto_now=True, blank=True), keep_default=False)

        # Adding field 'LineItem.last_modified'
        db.add_column(u'accounting_lineitem', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 506691), auto_now=True, blank=True), keep_default=False)

        # Adding field 'PaymentMethod.last_modified'
        db.add_column(u'accounting_paymentmethod', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 508002), auto_now=True, blank=True), keep_default=False)

        # Adding field 'Subscriber.last_modified'
        db.add_column(u'accounting_subscriber', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 502876), auto_now=True, blank=True), keep_default=False)

        # Adding field 'SoftwarePlan.last_modified'
        db.add_column(u'accounting_softwareplan', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 500193), auto_now=True, blank=True), keep_default=False)

        # Adding field 'CreditLine.last_modified'
        db.add_column(u'accounting_creditline', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 507317), auto_now=True, blank=True), keep_default=False)

        # Adding field 'BillingAccount.last_modified'
        db.add_column(u'accounting_billingaccount', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 496460), auto_now=True, blank=True), keep_default=False)

        # Adding field 'BillingContactInfo.last_modified'
        db.add_column(u'accounting_billingcontactinfo', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 497911), auto_now=True, blank=True), keep_default=False)

        # Adding field 'DefaultProductPlan.last_modified'
        db.add_column(u'accounting_defaultproductplan', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 500759), auto_now=True, blank=True), keep_default=False)

        # Adding field 'Feature.last_modified'
        db.add_column(u'accounting_feature', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 499258), auto_now=True, blank=True), keep_default=False)

        # Adding field 'CreditAdjustment.last_modified'
        db.add_column(u'accounting_creditadjustment', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 509052), auto_now=True, blank=True), keep_default=False)

        # Adding field 'BillingAccountAdmin.last_modified'
        db.add_column(u'accounting_billingaccountadmin', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 495911), auto_now=True, blank=True), keep_default=False)

        # Adding field 'FeatureRate.last_modified'
        db.add_column(u'accounting_featurerate', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 499703), auto_now=True, blank=True), keep_default=False)

        # Adding field 'SubscriptionAdjustment.last_modified'
        db.add_column(u'accounting_subscriptionadjustment', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 504944), auto_now=True, blank=True), keep_default=False)

        # Adding field 'SoftwarePlanVersion.last_modified'
        db.add_column(u'accounting_softwareplanversion', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 501361), auto_now=True, blank=True), keep_default=False)

        # Adding field 'PaymentRecord.last_modified'
        db.add_column(u'accounting_paymentrecord', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 508498), auto_now=True, blank=True), keep_default=False)

        # Adding field 'SoftwareProductRate.last_modified'
        db.add_column(u'accounting_softwareproductrate', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 498828), auto_now=True, blank=True), keep_default=False)

        # Adding field 'BillingRecord.last_modified'
        db.add_column(u'accounting_billingrecord', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 505703), auto_now=True, blank=True), keep_default=False)

        # Adding field 'Subscription.last_modified'
        db.add_column(u'accounting_subscription', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 503551), auto_now=True, blank=True), keep_default=False)

        # Adding field 'SoftwareProduct.last_modified'
        db.add_column(u'accounting_softwareproduct', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 4, 14, 9, 27, 12, 498391), auto_now=True, blank=True), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'Invoice.last_modified'
        db.delete_column(u'accounting_invoice', 'last_modified')

        # Deleting field 'LineItem.last_modified'
        db.delete_column(u'accounting_lineitem', 'last_modified')

        # Deleting field 'PaymentMethod.last_modified'
        db.delete_column(u'accounting_paymentmethod', 'last_modified')

        # Deleting field 'Subscriber.last_modified'
        db.delete_column(u'accounting_subscriber', 'last_modified')

        # Deleting field 'SoftwarePlan.last_modified'
        db.delete_column(u'accounting_softwareplan', 'last_modified')

        # Deleting field 'CreditLine.last_modified'
        db.delete_column(u'accounting_creditline', 'last_modified')

        # Deleting field 'BillingAccount.last_modified'
        db.delete_column(u'accounting_billingaccount', 'last_modified')

        # Deleting field 'BillingContactInfo.last_modified'
        db.delete_column(u'accounting_billingcontactinfo', 'last_modified')

        # Deleting field 'DefaultProductPlan.last_modified'
        db.delete_column(u'accounting_defaultproductplan', 'last_modified')

        # Deleting field 'Feature.last_modified'
        db.delete_column(u'accounting_feature', 'last_modified')

        # Deleting field 'CreditAdjustment.last_modified'
        db.delete_column(u'accounting_creditadjustment', 'last_modified')

        # Deleting field 'BillingAccountAdmin.last_modified'
        db.delete_column(u'accounting_billingaccountadmin', 'last_modified')

        # Deleting field 'FeatureRate.last_modified'
        db.delete_column(u'accounting_featurerate', 'last_modified')

        # Deleting field 'SubscriptionAdjustment.last_modified'
        db.delete_column(u'accounting_subscriptionadjustment', 'last_modified')

        # Deleting field 'SoftwarePlanVersion.last_modified'
        db.delete_column(u'accounting_softwareplanversion', 'last_modified')

        # Deleting field 'PaymentRecord.last_modified'
        db.delete_column(u'accounting_paymentrecord', 'last_modified')

        # Deleting field 'SoftwareProductRate.last_modified'
        db.delete_column(u'accounting_softwareproductrate', 'last_modified')

        # Deleting field 'BillingRecord.last_modified'
        db.delete_column(u'accounting_billingrecord', 'last_modified')

        # Deleting field 'Subscription.last_modified'
        db.delete_column(u'accounting_subscription', 'last_modified')

        # Deleting field 'SoftwareProduct.last_modified'
        db.delete_column(u'accounting_softwareproduct', 'last_modified')


    models = {
        u'accounting.billingaccount': {
            'Meta': {'object_name': 'BillingAccount'},
            'account_type': ('django.db.models.fields.CharField', [], {'default': "'CONTRACT'", 'max_length': '25'}),
            'billing_admins': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['accounting.BillingAccountAdmin']", 'null': 'True', 'symmetrical': 'False'}),
            'created_by': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'created_by_domain': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'blank': 'True'}),
            'currency': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Currency']"}),
            'date_confirmed_extra_charges': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'dimagi_contact': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True', 'blank': 'True'}),
            'entry_point': ('django.db.models.fields.CharField', [], {'default': "'NOT_SET'", 'max_length': '25'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_auto_invoiceable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 496460)', 'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'db_index': 'True'}),
            'salesforce_account_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '80', 'null': 'True', 'blank': 'True'})
        },
        u'accounting.billingaccountadmin': {
            'Meta': {'object_name': 'BillingAccountAdmin'},
            'domain': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '256', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 495911)', 'auto_now': 'True', 'blank': 'True'}),
            'web_user': ('django.db.models.fields.CharField', [], {'max_length': '80', 'db_index': 'True'})
        },
        u'accounting.billingcontactinfo': {
            'Meta': {'object_name': 'BillingContactInfo'},
            'account': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['accounting.BillingAccount']", 'unique': 'True', 'primary_key': 'True'}),
            'city': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'company_name': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'country': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'emails': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True'}),
            'first_line': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 497911)', 'auto_now': 'True', 'blank': 'True'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'phone_number': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'postal_code': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'second_line': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'state_province_region': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'accounting.billingrecord': {
            'Meta': {'object_name': 'BillingRecord'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'emailed_to': ('django.db.models.fields.CharField', [], {'max_length': '254', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invoice': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Invoice']"}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 505703)', 'auto_now': 'True', 'blank': 'True'}),
            'pdf_data_id': ('django.db.models.fields.CharField', [], {'max_length': '48'}),
            'skipped_email': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'accounting.creditadjustment': {
            'Meta': {'object_name': 'CreditAdjustment'},
            'amount': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'credit_line': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.CreditLine']"}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invoice': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Invoice']", 'null': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 509052)', 'auto_now': 'True', 'blank': 'True'}),
            'line_item': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.LineItem']", 'null': 'True'}),
            'note': ('django.db.models.fields.TextField', [], {}),
            'payment_record': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.PaymentRecord']", 'null': 'True'}),
            'reason': ('django.db.models.fields.CharField', [], {'default': "'MANUAL'", 'max_length': '25'}),
            'related_credit': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creditadjustment_related'", 'null': 'True', 'to': u"orm['accounting.CreditLine']"}),
            'web_user': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'})
        },
        u'accounting.creditline': {
            'Meta': {'object_name': 'CreditLine'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.BillingAccount']"}),
            'balance': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'feature_type': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 507317)', 'auto_now': 'True', 'blank': 'True'}),
            'product_type': ('django.db.models.fields.CharField', [], {'max_length': '25', 'null': 'True', 'blank': 'True'}),
            'subscription': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Subscription']", 'null': 'True', 'blank': 'True'})
        },
        u'accounting.currency': {
            'Meta': {'object_name': 'Currency'},
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '3'}),
            'date_updated': ('django.db.models.fields.DateField', [], {'auto_now': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_index': 'True'}),
            'rate_to_default': ('django.db.models.fields.DecimalField', [], {'default': "'1.0'", 'max_digits': '20', 'decimal_places': '9'}),
            'symbol': ('django.db.models.fields.CharField', [], {'max_length': '10'})
        },
        u'accounting.defaultproductplan': {
            'Meta': {'object_name': 'DefaultProductPlan'},
            'edition': ('django.db.models.fields.CharField', [], {'default': "'Community'", 'max_length': '25'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_trial': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 500759)', 'auto_now': 'True', 'blank': 'True'}),
            'plan': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwarePlan']"}),
            'product_type': ('django.db.models.fields.CharField', [], {'max_length': '25'})
        },
        u'accounting.feature': {
            'Meta': {'object_name': 'Feature'},
            'feature_type': ('django.db.models.fields.CharField', [], {'max_length': '10', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 499258)', 'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'})
        },
        u'accounting.featurerate': {
            'Meta': {'object_name': 'FeatureRate'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'feature': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Feature']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 499703)', 'auto_now': 'True', 'blank': 'True'}),
            'monthly_fee': ('django.db.models.fields.DecimalField', [], {'default': "'0.00'", 'max_digits': '10', 'decimal_places': '2'}),
            'monthly_limit': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'per_excess_fee': ('django.db.models.fields.DecimalField', [], {'default': "'0.00'", 'max_digits': '10', 'decimal_places': '2'})
        },
        u'accounting.invoice': {
            'Meta': {'object_name': 'Invoice'},
            'balance': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_due': ('django.db.models.fields.DateField', [], {'db_index': 'True'}),
            'date_end': ('django.db.models.fields.DateField', [], {}),
            'date_paid': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date_received': ('django.db.models.fields.DateField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'date_start': ('django.db.models.fields.DateField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_hidden': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_hidden_to_ops': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 504287)', 'auto_now': 'True', 'blank': 'True'}),
            'subscription': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Subscription']"}),
            'tax_rate': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'})
        },
        u'accounting.lineitem': {
            'Meta': {'object_name': 'LineItem'},
            'base_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'base_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'feature_rate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.FeatureRate']", 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invoice': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Invoice']"}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 506691)', 'auto_now': 'True', 'blank': 'True'}),
            'product_rate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwareProductRate']", 'null': 'True'}),
            'quantity': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'unit_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'unit_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        },
        u'accounting.paymentmethod': {
            'Meta': {'object_name': 'PaymentMethod'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.BillingAccount']"}),
            'billing_admin': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.BillingAccountAdmin']"}),
            'customer_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 508002)', 'auto_now': 'True', 'blank': 'True'}),
            'method_type': ('django.db.models.fields.CharField', [], {'default': "'Stripe'", 'max_length': '50', 'db_index': 'True'})
        },
        u'accounting.paymentrecord': {
            'Meta': {'object_name': 'PaymentRecord'},
            'amount': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 508498)', 'auto_now': 'True', 'blank': 'True'}),
            'payment_method': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.PaymentMethod']"}),
            'transaction_id': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        u'accounting.softwareplan': {
            'Meta': {'object_name': 'SoftwarePlan'},
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'edition': ('django.db.models.fields.CharField', [], {'default': "'Enterprise'", 'max_length': '25'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 500193)', 'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'visibility': ('django.db.models.fields.CharField', [], {'default': "'INTERNAL'", 'max_length': '10'})
        },
        u'accounting.softwareplanversion': {
            'Meta': {'object_name': 'SoftwarePlanVersion'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'feature_rates': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['accounting.FeatureRate']", 'symmetrical': 'False', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 501361)', 'auto_now': 'True', 'blank': 'True'}),
            'plan': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwarePlan']"}),
            'product_rates': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['accounting.SoftwareProductRate']", 'symmetrical': 'False', 'blank': 'True'}),
            'role': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['django_prbac.Role']"})
        },
        u'accounting.softwareproduct': {
            'Meta': {'object_name': 'SoftwareProduct'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 498391)', 'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'}),
            'product_type': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_index': 'True'})
        },
        u'accounting.softwareproductrate': {
            'Meta': {'object_name': 'SoftwareProductRate'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 498828)', 'auto_now': 'True', 'blank': 'True'}),
            'monthly_fee': ('django.db.models.fields.DecimalField', [], {'default': "'0.00'", 'max_digits': '10', 'decimal_places': '2'}),
            'product': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwareProduct']"})
        },
        u'accounting.subscriber': {
            'Meta': {'object_name': 'Subscriber'},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 502876)', 'auto_now': 'True', 'blank': 'True'}),
            'organization': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'db_index': 'True'})
        },
        u'accounting.subscription': {
            'Meta': {'object_name': 'Subscription'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.BillingAccount']"}),
            'auto_generate_credits': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_delay_invoicing': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date_end': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date_start': ('django.db.models.fields.DateField', [], {}),
            'do_not_invoice': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_trial': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 503551)', 'auto_now': 'True', 'blank': 'True'}),
            'plan_version': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwarePlanVersion']"}),
            'pro_bono_status': ('django.db.models.fields.CharField', [], {'default': "'NOT_SET'", 'max_length': '25'}),
            'salesforce_contract_id': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True', 'blank': 'True'}),
            'service_type': ('django.db.models.fields.CharField', [], {'default': "'NOT_SET'", 'max_length': '25'}),
            'subscriber': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Subscriber']"})
        },
        u'accounting.subscriptionadjustment': {
            'Meta': {'object_name': 'SubscriptionAdjustment'},
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invoice': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Invoice']", 'null': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 4, 14, 9, 27, 12, 504944)', 'auto_now': 'True', 'blank': 'True'}),
            'method': ('django.db.models.fields.CharField', [], {'default': "'INTERNAL'", 'max_length': '50'}),
            'new_date_delay_invoicing': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'new_date_end': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'new_date_start': ('django.db.models.fields.DateField', [], {}),
            'new_salesforce_contract_id': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True', 'blank': 'True'}),
            'note': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'reason': ('django.db.models.fields.CharField', [], {'default': "'CREATE'", 'max_length': '50'}),
            'related_subscription': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'subscriptionadjustment_related'", 'null': 'True', 'to': u"orm['accounting.Subscription']"}),
            'subscription': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Subscription']"}),
            'web_user': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'})
        },
        u'django_prbac.role': {
            'Meta': {'object_name': 'Role'},
            'description': ('django.db.models.fields.TextField', [], {'default': "u''", 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'parameters': ('django_prbac.fields.StringSetField', [], {'default': '[]', 'blank': 'True'}),
            'slug': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '256'})
        }
    }

    complete_apps = ['accounting']
