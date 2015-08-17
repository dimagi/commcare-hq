# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    depends_on = (
        ("django_prbac", "0001_initial"),
    )

    def forwards(self, orm):
        
        # Adding model 'Invoice'
        db.create_table(u'accounting_invoice', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('subscription', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.Subscription'])),
            ('tax_rate', self.gf('django.db.models.fields.DecimalField')(default='0.0000', max_digits=10, decimal_places=4)),
            ('balance', self.gf('django.db.models.fields.DecimalField')(default='0.0000', max_digits=10, decimal_places=4)),
            ('date_due', self.gf('django.db.models.fields.DateField')(db_index=True)),
            ('date_paid', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('date_created', self.gf('django.db.models.fields.DateField')(auto_now_add=True, blank=True)),
            ('date_received', self.gf('django.db.models.fields.DateField')(db_index=True, null=True, blank=True)),
            ('date_start', self.gf('django.db.models.fields.DateField')()),
            ('date_end', self.gf('django.db.models.fields.DateField')()),
        ))
        db.send_create_signal(u'accounting', ['Invoice'])

        # Adding model 'FeatureRate'
        db.create_table(u'accounting_featurerate', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('feature', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.Feature'])),
            ('monthly_fee', self.gf('django.db.models.fields.DecimalField')(default='0.0', max_digits=10, decimal_places=2)),
            ('monthly_limit', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('per_excess_fee', self.gf('django.db.models.fields.DecimalField')(default='0.0', max_digits=10, decimal_places=2)),
            ('date_created', self.gf('django.db.models.fields.DateField')(auto_now_add=True, blank=True)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal(u'accounting', ['FeatureRate'])

        # Adding model 'SoftwarePlan'
        db.create_table(u'accounting_softwareplan', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=80)),
            ('description', self.gf('django.db.models.fields.TextField')()),
            ('visibility', self.gf('django.db.models.fields.CharField')(default='INTERNAL', max_length=10)),
        ))
        db.send_create_signal(u'accounting', ['SoftwarePlan'])

        # Adding model 'CreditLine'
        db.create_table(u'accounting_creditline', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.BillingAccount'])),
            ('subscription', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.Subscription'], null=True, blank=True)),
            ('product_rate', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.SoftwareProductRate'], null=True, blank=True)),
            ('feature_rate', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.FeatureRate'], null=True, blank=True)),
            ('date_created', self.gf('django.db.models.fields.DateField')(auto_now_add=True, blank=True)),
            ('balance', self.gf('django.db.models.fields.DecimalField')(default='0.0000', max_digits=10, decimal_places=4)),
        ))
        db.send_create_signal(u'accounting', ['CreditLine'])

        # Adding model 'BillingAccount'
        db.create_table(u'accounting_billingaccount', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=40, db_index=True)),
            ('salesforce_account_id', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=80, null=True, blank=True)),
            ('created_by', self.gf('django.db.models.fields.CharField')(max_length=80)),
            ('date_created', self.gf('django.db.models.fields.DateField')(auto_now_add=True, blank=True)),
            ('web_user_contact', self.gf('django.db.models.fields.CharField')(max_length=80, null=True)),
            ('currency', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.Currency'])),
            ('is_auto_invoiceable', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('account_type', self.gf('django.db.models.fields.CharField')(default='CONTRACT', max_length=25)),
        ))
        db.send_create_signal(u'accounting', ['BillingAccount'])

        # Adding model 'DefaultProductPlan'
        db.create_table(u'accounting_defaultproductplan', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('product_type', self.gf('django.db.models.fields.CharField')(unique=True, max_length=25)),
            ('plan', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.SoftwarePlan'])),
        ))
        db.send_create_signal(u'accounting', ['DefaultProductPlan'])

        # Adding model 'Feature'
        db.create_table(u'accounting_feature', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=40)),
            ('feature_type', self.gf('django.db.models.fields.CharField')(max_length=10, db_index=True)),
        ))
        db.send_create_signal(u'accounting', ['Feature'])

        # Adding model 'CreditAdjustment'
        db.create_table(u'accounting_creditadjustment', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('credit_line', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.CreditLine'])),
            ('reason', self.gf('django.db.models.fields.CharField')(default='MANUAL', max_length=25)),
            ('note', self.gf('django.db.models.fields.TextField')()),
            ('amount', self.gf('django.db.models.fields.DecimalField')(default='0.0000', max_digits=10, decimal_places=4)),
            ('line_item', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.LineItem'], null=True)),
            ('invoice', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.Invoice'], null=True)),
            ('date_created', self.gf('django.db.models.fields.DateField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal(u'accounting', ['CreditAdjustment'])

        # Adding model 'SoftwarePlanVersion'
        db.create_table(u'accounting_softwareplanversion', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('plan', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.SoftwarePlan'])),
            ('date_created', self.gf('django.db.models.fields.DateField')(auto_now_add=True, blank=True)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('role', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['django_prbac.Role'])),
        ))
        db.send_create_signal(u'accounting', ['SoftwarePlanVersion'])

        # Adding M2M table for field product_rates on 'SoftwarePlanVersion'
        db.create_table(u'accounting_softwareplanversion_product_rates', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('softwareplanversion', models.ForeignKey(orm[u'accounting.softwareplanversion'], null=False)),
            ('softwareproductrate', models.ForeignKey(orm[u'accounting.softwareproductrate'], null=False))
        ))
        db.create_unique(u'accounting_softwareplanversion_product_rates', ['softwareplanversion_id', 'softwareproductrate_id'])

        # Adding M2M table for field feature_rates on 'SoftwarePlanVersion'
        db.create_table(u'accounting_softwareplanversion_feature_rates', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('softwareplanversion', models.ForeignKey(orm[u'accounting.softwareplanversion'], null=False)),
            ('featurerate', models.ForeignKey(orm[u'accounting.featurerate'], null=False))
        ))
        db.create_unique(u'accounting_softwareplanversion_feature_rates', ['softwareplanversion_id', 'featurerate_id'])

        # Adding model 'LineItem'
        db.create_table(u'accounting_lineitem', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('invoice', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.Invoice'])),
            ('feature_rate', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.FeatureRate'], null=True)),
            ('product_rate', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.SoftwareProductRate'], null=True)),
            ('base_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('base_cost', self.gf('django.db.models.fields.DecimalField')(default='0.0000', max_digits=10, decimal_places=4)),
            ('unit_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('unit_cost', self.gf('django.db.models.fields.DecimalField')(default='0.0000', max_digits=10, decimal_places=4)),
            ('quantity', self.gf('django.db.models.fields.IntegerField')(default=1)),
        ))
        db.send_create_signal(u'accounting', ['LineItem'])

        # Adding model 'Subscriber'
        db.create_table(u'accounting_subscriber', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=25, null=True, db_index=True)),
            ('organization', self.gf('django.db.models.fields.CharField')(max_length=25, null=True, db_index=True)),
        ))
        db.send_create_signal(u'accounting', ['Subscriber'])

        # Adding model 'SoftwareProductRate'
        db.create_table(u'accounting_softwareproductrate', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('product', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.SoftwareProduct'])),
            ('monthly_fee', self.gf('django.db.models.fields.DecimalField')(default='0.0', max_digits=10, decimal_places=2)),
            ('date_created', self.gf('django.db.models.fields.DateField')(auto_now_add=True, blank=True)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal(u'accounting', ['SoftwareProductRate'])

        # Adding model 'BillingRecord'
        db.create_table(u'accounting_billingrecord', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('invoice', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.Invoice'])),
            ('date_emailed', self.gf('django.db.models.fields.DateField')(auto_now_add=True, db_index=True, blank=True)),
            ('emailed_to', self.gf('django.db.models.fields.CharField')(max_length=254, db_index=True)),
            ('pdf_data_id', self.gf('django.db.models.fields.CharField')(max_length=48)),
        ))
        db.send_create_signal(u'accounting', ['BillingRecord'])

        # Adding model 'Subscription'
        db.create_table(u'accounting_subscription', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.BillingAccount'])),
            ('plan_version', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.SoftwarePlanVersion'])),
            ('subscriber', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounting.Subscriber'])),
            ('salesforce_contract_id', self.gf('django.db.models.fields.CharField')(max_length=80, null=True, blank=True)),
            ('date_start', self.gf('django.db.models.fields.DateField')()),
            ('date_end', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('date_delay_invoicing', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('date_created', self.gf('django.db.models.fields.DateField')(auto_now_add=True, blank=True)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'accounting', ['Subscription'])

        # Adding model 'SoftwareProduct'
        db.create_table(u'accounting_softwareproduct', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=40)),
            ('product_type', self.gf('django.db.models.fields.CharField')(max_length=25, db_index=True)),
        ))
        db.send_create_signal(u'accounting', ['SoftwareProduct'])


    def backwards(self, orm):
        
        # Deleting model 'Invoice'
        db.delete_table(u'accounting_invoice')

        # Deleting model 'FeatureRate'
        db.delete_table(u'accounting_featurerate')

        # Deleting model 'SoftwarePlan'
        db.delete_table(u'accounting_softwareplan')

        # Deleting model 'CreditLine'
        db.delete_table(u'accounting_creditline')

        # Deleting model 'BillingAccount'
        db.delete_table(u'accounting_billingaccount')

        # Deleting model 'DefaultProductPlan'
        db.delete_table(u'accounting_defaultproductplan')

        # Deleting model 'Feature'
        db.delete_table(u'accounting_feature')

        # Deleting model 'CreditAdjustment'
        db.delete_table(u'accounting_creditadjustment')

        # Deleting model 'SoftwarePlanVersion'
        db.delete_table(u'accounting_softwareplanversion')

        # Removing M2M table for field product_rates on 'SoftwarePlanVersion'
        db.delete_table('accounting_softwareplanversion_product_rates')

        # Removing M2M table for field feature_rates on 'SoftwarePlanVersion'
        db.delete_table('accounting_softwareplanversion_feature_rates')

        # Deleting model 'LineItem'
        db.delete_table(u'accounting_lineitem')

        # Deleting model 'Subscriber'
        db.delete_table(u'accounting_subscriber')

        # Deleting model 'SoftwareProductRate'
        db.delete_table(u'accounting_softwareproductrate')

        # Deleting model 'BillingRecord'
        db.delete_table(u'accounting_billingrecord')

        # Deleting model 'Subscription'
        db.delete_table(u'accounting_subscription')

        # Deleting model 'SoftwareProduct'
        db.delete_table(u'accounting_softwareproduct')


    models = {
        u'accounting.billingaccount': {
            'Meta': {'object_name': 'BillingAccount'},
            'account_type': ('django.db.models.fields.CharField', [], {'default': "'CONTRACT'", 'max_length': '25'}),
            'created_by': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'currency': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Currency']"}),
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_auto_invoiceable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '40', 'db_index': 'True'}),
            'salesforce_account_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '80', 'null': 'True', 'blank': 'True'}),
            'web_user_contact': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'})
        },
        u'accounting.billingrecord': {
            'Meta': {'object_name': 'BillingRecord'},
            'date_emailed': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'emailed_to': ('django.db.models.fields.CharField', [], {'max_length': '254', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invoice': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Invoice']"}),
            'pdf_data_id': ('django.db.models.fields.CharField', [], {'max_length': '48'})
        },
        u'accounting.creditadjustment': {
            'Meta': {'object_name': 'CreditAdjustment'},
            'amount': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'credit_line': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.CreditLine']"}),
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invoice': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Invoice']", 'null': 'True'}),
            'line_item': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.LineItem']", 'null': 'True'}),
            'note': ('django.db.models.fields.TextField', [], {}),
            'reason': ('django.db.models.fields.CharField', [], {'default': "'MANUAL'", 'max_length': '25'})
        },
        u'accounting.creditline': {
            'Meta': {'object_name': 'CreditLine'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.BillingAccount']"}),
            'balance': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'feature_rate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.FeatureRate']", 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'product_rate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwareProductRate']", 'null': 'True', 'blank': 'True'}),
            'subscription': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Subscription']", 'null': 'True', 'blank': 'True'})
        },
        u'accounting.currency': {
            'Meta': {'object_name': 'Currency'},
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '3'}),
            'date_updated': ('django.db.models.fields.DateField', [], {'auto_now': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_index': 'True'}),
            'rate_to_default': ('django.db.models.fields.DecimalField', [], {'default': '1.0', 'max_digits': '20', 'decimal_places': '9'}),
            'symbol': ('django.db.models.fields.CharField', [], {'max_length': '10'})
        },
        u'accounting.defaultproductplan': {
            'Meta': {'object_name': 'DefaultProductPlan'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'plan': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwarePlan']"}),
            'product_type': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '25'})
        },
        u'accounting.feature': {
            'Meta': {'object_name': 'Feature'},
            'feature_type': ('django.db.models.fields.CharField', [], {'max_length': '10', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'})
        },
        u'accounting.featurerate': {
            'Meta': {'object_name': 'FeatureRate'},
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'feature': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Feature']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'monthly_fee': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '10', 'decimal_places': '2'}),
            'monthly_limit': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'per_excess_fee': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '10', 'decimal_places': '2'})
        },
        u'accounting.invoice': {
            'Meta': {'object_name': 'Invoice'},
            'balance': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_due': ('django.db.models.fields.DateField', [], {'db_index': 'True'}),
            'date_end': ('django.db.models.fields.DateField', [], {}),
            'date_paid': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date_received': ('django.db.models.fields.DateField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'date_start': ('django.db.models.fields.DateField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
            'product_rate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwareProductRate']", 'null': 'True'}),
            'quantity': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'unit_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'unit_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        },
        u'accounting.softwareplan': {
            'Meta': {'object_name': 'SoftwarePlan'},
            'description': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'visibility': ('django.db.models.fields.CharField', [], {'default': "'INTERNAL'", 'max_length': '10'})
        },
        u'accounting.softwareplanversion': {
            'Meta': {'object_name': 'SoftwarePlanVersion'},
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'feature_rates': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['accounting.FeatureRate']", 'symmetrical': 'False', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'plan': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwarePlan']"}),
            'product_rates': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['accounting.SoftwareProductRate']", 'symmetrical': 'False', 'blank': 'True'}),
            'role': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['django_prbac.Role']"})
        },
        u'accounting.softwareproduct': {
            'Meta': {'object_name': 'SoftwareProduct'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'}),
            'product_type': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_index': 'True'})
        },
        u'accounting.softwareproductrate': {
            'Meta': {'object_name': 'SoftwareProductRate'},
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'monthly_fee': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '10', 'decimal_places': '2'}),
            'product': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwareProduct']"})
        },
        u'accounting.subscriber': {
            'Meta': {'object_name': 'Subscriber'},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '25', 'null': 'True', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'organization': ('django.db.models.fields.CharField', [], {'max_length': '25', 'null': 'True', 'db_index': 'True'})
        },
        u'accounting.subscription': {
            'Meta': {'object_name': 'Subscription'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.BillingAccount']"}),
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_delay_invoicing': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date_end': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date_start': ('django.db.models.fields.DateField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'plan_version': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwarePlanVersion']"}),
            'salesforce_contract_id': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True', 'blank': 'True'}),
            'subscriber': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Subscriber']"})
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
