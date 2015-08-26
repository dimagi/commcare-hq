# -*- coding: utf-8 -*-
from south.db import db
from south.v2 import DataMigration
from django.db import connection


class Migration(DataMigration):

    def forwards(self, orm):
        """
        Django doesn't allow joins within mass-update queries, so doing something like
        `orm['accounting.paymentmethod'].all().update(web_user=F('billing_admin__web_user')`
        throws a FieldError.
        Even though this is a small table, I left this query like this instead of
        looping and saving each entry alone.

        The second query takes each duplicate paymentmethod and adds -duplicate to it.
        In the current model, payment methods are unique per billingaccount.
        With this change, we allow domain admins to make payments for any account they
        have access to.
        """

        sql = """
            UPDATE accounting_paymentmethod
            SET web_user = accounting_billingaccountadmin.web_user
            FROM accounting_billingaccountadmin
            WHERE accounting_paymentmethod.billing_admin_id = accounting_billingaccountadmin.id;

            UPDATE accounting_paymentmethod
            SET method_type = method_type || '-duplicate'
            WHERE id IN (SELECT id
                          FROM (SELECT id, row_number() over (partition BY web_user ORDER BY id) AS rnum
                                 FROM accounting_paymentmethod) t
                          WHERE t.rnum > 1);
        """

        cursor = connection.cursor()
        cursor.execute(sql)

    def backwards(self, orm):
        sql = """
            UPDATE accounting_paymentmethod
            SET method_type = 'Stripe'
            WHERE method_type = 'Stripe-duplicate'
        """
        cursor = connection.cursor()
        cursor.execute(sql)


    models = {
        u'accounting.billingaccount': {
            'Meta': {'object_name': 'BillingAccount'},
            'account_type': ('django.db.models.fields.CharField', [], {'default': "'CONTRACT'", 'max_length': '25'}),
            'billing_admins': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['accounting.BillingAccountAdmin']", 'null': 'True', 'symmetrical': 'False'}),
            'created_by': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'created_by_domain': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'blank': 'True'}),
            'currency': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Currency']", 'on_delete': 'models.PROTECT'}),
            'date_confirmed_extra_charges': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'dimagi_contact': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True', 'blank': 'True'}),
            'entry_point': ('django.db.models.fields.CharField', [], {'default': "'NOT_SET'", 'max_length': '25'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_auto_invoiceable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'db_index': 'True'}),
            'salesforce_account_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '80', 'null': 'True', 'blank': 'True'})
        },
        u'accounting.billingaccountadmin': {
            'Meta': {'object_name': 'BillingAccountAdmin'},
            'domain': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '256', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
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
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
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
            'invoice': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Invoice']", 'on_delete': 'models.PROTECT'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'pdf_data_id': ('django.db.models.fields.CharField', [], {'max_length': '48'}),
            'skipped_email': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'accounting.creditadjustment': {
            'Meta': {'object_name': 'CreditAdjustment'},
            'amount': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'credit_line': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.CreditLine']", 'on_delete': 'models.PROTECT'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invoice': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Invoice']", 'null': 'True', 'on_delete': 'models.PROTECT'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'line_item': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.LineItem']", 'null': 'True', 'on_delete': 'models.PROTECT'}),
            'note': ('django.db.models.fields.TextField', [], {}),
            'payment_record': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.PaymentRecord']", 'null': 'True', 'on_delete': 'models.PROTECT'}),
            'reason': ('django.db.models.fields.CharField', [], {'default': "'MANUAL'", 'max_length': '25'}),
            'related_credit': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creditadjustment_related'", 'null': 'True', 'on_delete': 'models.PROTECT', 'to': u"orm['accounting.CreditLine']"}),
            'web_user': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'})
        },
        u'accounting.creditline': {
            'Meta': {'object_name': 'CreditLine'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.BillingAccount']", 'on_delete': 'models.PROTECT'}),
            'balance': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'feature_type': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'product_type': ('django.db.models.fields.CharField', [], {'max_length': '25', 'null': 'True', 'blank': 'True'}),
            'subscription': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Subscription']", 'null': 'True', 'on_delete': 'models.PROTECT', 'blank': 'True'})
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
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'plan': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwarePlan']", 'on_delete': 'models.PROTECT'}),
            'product_type': ('django.db.models.fields.CharField', [], {'max_length': '25'})
        },
        u'accounting.feature': {
            'Meta': {'object_name': 'Feature'},
            'feature_type': ('django.db.models.fields.CharField', [], {'max_length': '10', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'})
        },
        u'accounting.featurerate': {
            'Meta': {'object_name': 'FeatureRate'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'feature': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Feature']", 'on_delete': 'models.PROTECT'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'monthly_fee': ('django.db.models.fields.DecimalField', [], {'default': "'0.00'", 'max_digits': '10', 'decimal_places': '2'}),
            'monthly_limit': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'per_excess_fee': ('django.db.models.fields.DecimalField', [], {'default': "'0.00'", 'max_digits': '10', 'decimal_places': '2'})
        },
        u'accounting.invoice': {
            'Meta': {'object_name': 'Invoice'},
            'balance': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_due': ('django.db.models.fields.DateField', [], {'null': 'True', 'db_index': 'True'}),
            'date_end': ('django.db.models.fields.DateField', [], {}),
            'date_paid': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date_received': ('django.db.models.fields.DateField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'date_start': ('django.db.models.fields.DateField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_hidden': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_hidden_to_ops': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'subscription': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Subscription']", 'on_delete': 'models.PROTECT'}),
            'tax_rate': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'})
        },
        u'accounting.lineitem': {
            'Meta': {'object_name': 'LineItem'},
            'base_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'base_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'feature_rate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.FeatureRate']", 'null': 'True', 'on_delete': 'models.PROTECT'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invoice': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Invoice']", 'on_delete': 'models.PROTECT'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'product_rate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwareProductRate']", 'null': 'True', 'on_delete': 'models.PROTECT'}),
            'quantity': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'unit_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'unit_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        },
        u'accounting.paymentmethod': {
            'Meta': {'object_name': 'PaymentMethod'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.BillingAccount']", 'on_delete': 'models.PROTECT'}),
            'billing_admin': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.BillingAccountAdmin']", 'on_delete': 'models.PROTECT'}),
            'customer_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'method_type': ('django.db.models.fields.CharField', [], {'default': "'Stripe'", 'max_length': '50', 'db_index': 'True'}),
            'web_user': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'})
        },
        u'accounting.paymentrecord': {
            'Meta': {'object_name': 'PaymentRecord'},
            'amount': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'payment_method': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.PaymentMethod']", 'on_delete': 'models.PROTECT'}),
            'transaction_id': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        u'accounting.softwareplan': {
            'Meta': {'object_name': 'SoftwarePlan'},
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'edition': ('django.db.models.fields.CharField', [], {'default': "'Enterprise'", 'max_length': '25'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'visibility': ('django.db.models.fields.CharField', [], {'default': "'INTERNAL'", 'max_length': '10'})
        },
        u'accounting.softwareplanversion': {
            'Meta': {'object_name': 'SoftwarePlanVersion'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'feature_rates': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['accounting.FeatureRate']", 'symmetrical': 'False', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'plan': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwarePlan']", 'on_delete': 'models.PROTECT'}),
            'product_rates': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['accounting.SoftwareProductRate']", 'symmetrical': 'False', 'blank': 'True'}),
            'role': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['django_prbac.Role']"})
        },
        u'accounting.softwareproduct': {
            'Meta': {'object_name': 'SoftwareProduct'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'}),
            'product_type': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_index': 'True'})
        },
        u'accounting.softwareproductrate': {
            'Meta': {'object_name': 'SoftwareProductRate'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'monthly_fee': ('django.db.models.fields.DecimalField', [], {'default': "'0.00'", 'max_digits': '10', 'decimal_places': '2'}),
            'product': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwareProduct']", 'on_delete': 'models.PROTECT'})
        },
        u'accounting.subscriber': {
            'Meta': {'object_name': 'Subscriber'},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'organization': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'db_index': 'True'})
        },
        u'accounting.subscription': {
            'Meta': {'object_name': 'Subscription'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.BillingAccount']", 'on_delete': 'models.PROTECT'}),
            'auto_generate_credits': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_delay_invoicing': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date_end': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date_start': ('django.db.models.fields.DateField', [], {}),
            'do_not_invoice': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_trial': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'plan_version': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwarePlanVersion']", 'on_delete': 'models.PROTECT'}),
            'pro_bono_status': ('django.db.models.fields.CharField', [], {'default': "'NOT_SET'", 'max_length': '25'}),
            'salesforce_contract_id': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True', 'blank': 'True'}),
            'service_type': ('django.db.models.fields.CharField', [], {'default': "'NOT_SET'", 'max_length': '25'}),
            'subscriber': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Subscriber']", 'on_delete': 'models.PROTECT'})
        },
        u'accounting.subscriptionadjustment': {
            'Meta': {'object_name': 'SubscriptionAdjustment'},
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invoice': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Invoice']", 'null': 'True', 'on_delete': 'models.PROTECT'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'method': ('django.db.models.fields.CharField', [], {'default': "'INTERNAL'", 'max_length': '50'}),
            'new_date_delay_invoicing': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'new_date_end': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'new_date_start': ('django.db.models.fields.DateField', [], {}),
            'new_salesforce_contract_id': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True', 'blank': 'True'}),
            'note': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'reason': ('django.db.models.fields.CharField', [], {'default': "'CREATE'", 'max_length': '50'}),
            'related_subscription': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'subscriptionadjustment_related'", 'null': 'True', 'on_delete': 'models.PROTECT', 'to': u"orm['accounting.Subscription']"}),
            'subscription': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Subscription']", 'on_delete': 'models.PROTECT'}),
            'web_user': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'})
        },
        u'accounting.wirebillingrecord': {
            'Meta': {'object_name': 'WireBillingRecord'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'emailed_to': ('django.db.models.fields.CharField', [], {'max_length': '254', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invoice': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.WireInvoice']", 'on_delete': 'models.PROTECT'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'pdf_data_id': ('django.db.models.fields.CharField', [], {'max_length': '48'}),
            'skipped_email': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'accounting.wireinvoice': {
            'Meta': {'object_name': 'WireInvoice'},
            'balance': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_due': ('django.db.models.fields.DateField', [], {'null': 'True', 'db_index': 'True'}),
            'date_end': ('django.db.models.fields.DateField', [], {}),
            'date_paid': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date_received': ('django.db.models.fields.DateField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'date_start': ('django.db.models.fields.DateField', [], {}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_hidden': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_hidden_to_ops': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'tax_rate': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'})
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
    symmetrical = True
