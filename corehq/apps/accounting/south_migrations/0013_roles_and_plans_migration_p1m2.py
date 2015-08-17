# encoding: utf-8
from collections import defaultdict
import datetime
from decimal import Decimal
import logging
from django.core.exceptions import ObjectDoesNotExist
from django.core.management import call_command
from south.db import db
from south.v2 import DataMigration
from django.db import models
from corehq.apps.accounting.models import (
    FeatureType, SoftwarePlanEdition, SoftwareProductType,
    SoftwarePlanVisibility,
)

logger = logging.getLogger(__name__)


class Migration(DataMigration):

    def forwards(self, orm):
        call_command('cchq_prbac_bootstrap')
        boostrap_handler = BootstrapSoftwarePlans(orm)
        boostrap_handler.bootstrap()

        # Reset Subscription plan_version to the latest version for that plan
        for subscription in orm.Subscription.objects.all():
            software_plan = subscription.plan_version.plan
            latest_version = software_plan.softwareplanversion_set.filter(
                is_active=True
            ).latest('date_created')
            if subscription.plan_version.pk != latest_version.pk:
                logger.info("%s reset to newest version."
                            % subscription.subscriber.domain)
                subscription.plan_version = latest_version
                subscription.save()

        # make sure that the default standard plan SMS FeatureRate
        # has the monthly_limit set to 100
        standard_plans = orm.DefaultProductPlan.objects.filter(
            edition=SoftwarePlanEdition.STANDARD)
        for std_plan in standard_plans:
            feature_rate = std_plan.plan.softwareplanversion_set.filter(
                is_active=True
            ).latest('date_created').feature_rates.filter(
                feature__feature_type=FeatureType.SMS
            )[0]
            if feature_rate.monthly_limit != 100:
                feature_rate.monthly_limit = 100
                feature_rate.save()

        for plan in orm.SoftwarePlan.objects.all():
            default_version = plan.softwareplanversion_set.filter(
                is_active=True
            ).latest('date_created')
            for version in plan.softwareplanversion_set.all():
                if version.pk != default_version.pk:
                    try:
                        version.delete()
                    except models.ProtectedError:
                        logger.info("Skipped deleting SoftwarePlanVersion "
                                    "with id %d for plan %s because it was "
                                    "still being used."
                                    % (version.pk, plan.name))

        for credit_line in orm.CreditLine.objects.filter(feature_rate__isnull=False).all():
            latest_rate = credit_line.feature_rate.feature.get_rate()
            if credit_line.feature_rate.pk != latest_rate.pk:
                credit_line.feature_rate = latest_rate
                credit_line.save()

        for feature_rate in orm.FeatureRate.objects.all():
            if feature_rate.softwareplanversion_set.count() == 0:
                try:
                    feature_rate.delete()
                except models.ProtectedError:
                    logger.info("Skipped deleting FeatureRate with id "
                                "%d because it was still being used."
                                % feature_rate.pk)

        for credit_line in orm.CreditLine.objects.filter(product_rate__isnull=False).all():
            latest_rate = credit_line.product_rate.product.get_rate()
            if credit_line.product_rate.pk != latest_rate.pk:
                credit_line.product_rate = latest_rate
                credit_line.save()

        for product_rate in orm.SoftwareProductRate.objects.all():
            if product_rate.softwareplanversion_set.count() == 0:
                try:
                    product_rate.delete()
                except models.ProtectedError:
                    logger.info("Skipped deleting ProductRate with id "
                                "%d because it was still being used."
                                % product_rate.pk)

    def backwards(self, orm):
        pass



    models = {
        u'accounting.billingaccount': {
            'Meta': {'object_name': 'BillingAccount'},
            'account_type': ('django.db.models.fields.CharField', [], {'default': "'CONTRACT'", 'max_length': '25'}),
            'billing_admins': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['accounting.BillingAccountAdmin']", 'null': 'True', 'symmetrical': 'False'}),
            'created_by': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'created_by_domain': ('django.db.models.fields.CharField', [], {'max_length': '25', 'null': 'True', 'blank': 'True'}),
            'currency': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Currency']"}),
            'date_confirmed_extra_charges': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_auto_invoiceable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'db_index': 'True'}),
            'salesforce_account_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '80', 'null': 'True', 'blank': 'True'})
        },
        u'accounting.billingaccountadmin': {
            'Meta': {'object_name': 'BillingAccountAdmin'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'web_user': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80', 'db_index': 'True'})
        },
        u'accounting.billingcontactinfo': {
            'Meta': {'object_name': 'BillingContactInfo'},
            'account': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['accounting.BillingAccount']", 'unique': 'True', 'primary_key': 'True'}),
            'city': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'company_name': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'country': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'emails': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'first_line': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'phone_number': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'postal_code': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'second_line': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'state_province_region': ('django.db.models.fields.CharField', [], {'max_length': '50'})
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
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invoice': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Invoice']", 'null': 'True'}),
            'line_item': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.LineItem']", 'null': 'True'}),
            'note': ('django.db.models.fields.TextField', [], {}),
            'reason': ('django.db.models.fields.CharField', [], {'default': "'MANUAL'", 'max_length': '25'}),
            'web_user': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'})
        },
        u'accounting.creditline': {
            'Meta': {'object_name': 'CreditLine'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.BillingAccount']"}),
            'balance': ('django.db.models.fields.DecimalField', [], {'default': "'0.0000'", 'max_digits': '10', 'decimal_places': '4'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
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
            'rate_to_default': ('django.db.models.fields.DecimalField', [], {'default': "'1.0'", 'max_digits': '20', 'decimal_places': '9'}),
            'symbol': ('django.db.models.fields.CharField', [], {'max_length': '10'})
        },
        u'accounting.defaultproductplan': {
            'Meta': {'object_name': 'DefaultProductPlan'},
            'edition': ('django.db.models.fields.CharField', [], {'default': "'Community'", 'max_length': '25'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'plan': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwarePlan']"}),
            'product_type': ('django.db.models.fields.CharField', [], {'max_length': '25'})
        },
        u'accounting.feature': {
            'Meta': {'object_name': 'Feature'},
            'feature_type': ('django.db.models.fields.CharField', [], {'max_length': '10', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'})
        },
        u'accounting.featurerate': {
            'Meta': {'object_name': 'FeatureRate'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'feature': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Feature']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
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
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'edition': ('django.db.models.fields.CharField', [], {'default': "'Enterprise'", 'max_length': '25'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'visibility': ('django.db.models.fields.CharField', [], {'default': "'INTERNAL'", 'max_length': '10'})
        },
        u'accounting.softwareplanversion': {
            'Meta': {'object_name': 'SoftwarePlanVersion'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
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
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'monthly_fee': ('django.db.models.fields.DecimalField', [], {'default': "'0.00'", 'max_digits': '10', 'decimal_places': '2'}),
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
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_delay_invoicing': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date_end': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date_start': ('django.db.models.fields.DateField', [], {}),
            'do_not_invoice': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'plan_version': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.SoftwarePlanVersion']"}),
            'salesforce_contract_id': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True', 'blank': 'True'}),
            'subscriber': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Subscriber']"})
        },
        u'accounting.subscriptionadjustment': {
            'Meta': {'object_name': 'SubscriptionAdjustment'},
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invoice': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['accounting.Invoice']", 'null': 'True'}),
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


class BootstrapSoftwarePlans(object):
    """
    This is a direct copy of the cchq_software_plan_bootstrap management command
    so that orm can be used to reference the objects.
    """
    def __init__(self, orm):
        self.orm = orm
        self.verbose = False
        self.for_tests = False

    def bootstrap(self):
        logger.info('Bootstrapping standard plans. Enterprise plans will have to be created via the admin UIs.')

        self.product_types = [p[0] for p in SoftwareProductType.CHOICES]
        self.editions = [
            SoftwarePlanEdition.COMMUNITY,
            SoftwarePlanEdition.STANDARD,
            SoftwarePlanEdition.PRO,
            SoftwarePlanEdition.ADVANCED,
            SoftwarePlanEdition.ENTERPRISE,
        ]
        self.feature_types = [f[0] for f in FeatureType.CHOICES]
        self.ensure_plans()

    def ensure_plans(self, dry_run=False):
        edition_to_features = self.ensure_features(dry_run=dry_run)
        for product_type in self.product_types:
            for edition in self.editions:
                role_slug = self.BOOTSTRAP_EDITION_TO_ROLE[edition]
                try:
                    role = self.orm['django_prbac.Role'].objects.get(slug=role_slug)
                except ObjectDoesNotExist:
                    logger.info("Could not find the role '%s'. Did you forget to run cchq_prbac_bootstrap?")
                    logger.info("Aborting. You should figure this out.")
                    return
                software_plan_version = self.orm.SoftwarePlanVersion(role=role)

                product, product_rates = self.ensure_product_and_rate(product_type, edition, dry_run=dry_run)
                feature_rates = self.ensure_feature_rates(edition_to_features[edition], edition, dry_run=dry_run)
                software_plan = self.orm.SoftwarePlan(
                    name='%s Edition' % product.name, edition=edition, visibility=SoftwarePlanVisibility.PUBLIC
                )
                if dry_run:
                    logger.info("[DRY RUN] Creating Software Plan: %s" % software_plan.name)
                else:
                    try:
                        software_plan = self.orm.SoftwarePlan.objects.get(name=software_plan.name)
                        if self.verbose:
                            logger.info("Plan '%s' already exists. Using existing plan to add version."
                                        % software_plan.name)
                    except self.orm.SoftwarePlan.DoesNotExist:
                        software_plan.save()
                        if self.verbose:
                            logger.info("Creating Software Plan: %s" % software_plan.name)

                        software_plan_version.plan = software_plan
                        software_plan_version.save()
                        for product_rate in product_rates:
                            product_rate.save()
                            software_plan_version.product_rates.add(product_rate)
                        for feature_rate in feature_rates:
                            feature_rate.save()
                            software_plan_version.feature_rates.add(feature_rate)
                        software_plan_version.save()

                default_product_plan = self.orm.DefaultProductPlan(product_type=product.product_type, edition=edition)
                if dry_run:
                    logger.info("[DRY RUN] Setting plan as default for product '%s' and edition '%s'." %
                                 (product.product_type, default_product_plan.edition))
                else:
                    try:
                        default_product_plan = self.orm.DefaultProductPlan.objects.get(
                            product_type=product.product_type, edition=edition
                        )
                        if self.verbose:
                            logger.info("Default for product '%s' and edition "
                                        "'%s' already exists." % (
                                product.product_type, default_product_plan.edition
                            ))
                    except ObjectDoesNotExist:
                        default_product_plan.plan = software_plan
                        default_product_plan.save()
                        if self.verbose:
                            logger.info("Setting plan as default for product '%s' and edition '%s'." %
                                        (product.product_type,
                                         default_product_plan.edition))

    def ensure_product_and_rate(self, product_type, edition, dry_run=False):
        """
        Ensures that all the necessary SoftwareProducts and SoftwareProductRates are created for the plan.
        """
        if self.verbose:
            logger.info('Ensuring Products and Product Rates')

        product = self.orm.SoftwareProduct(name='%s %s' % (product_type, edition), product_type=product_type)
        if edition == SoftwarePlanEdition.ENTERPRISE:
            product.name = "Dimagi Only %s" % product.name

        product_rates = []
        BOOTSTRAP_PRODUCT_RATES = {
            SoftwarePlanEdition.COMMUNITY: [
                self.orm.SoftwareProductRate(),  # use all the defaults
            ],
            SoftwarePlanEdition.STANDARD: [
                self.orm.SoftwareProductRate(monthly_fee=Decimal('100.00')),
            ],
            SoftwarePlanEdition.PRO: [
                self.orm.SoftwareProductRate(monthly_fee=Decimal('500.00')),
            ],
            SoftwarePlanEdition.ADVANCED: [
                self.orm.SoftwareProductRate(monthly_fee=Decimal('1000.00')),
            ],
            SoftwarePlanEdition.ENTERPRISE: [
                self.orm.SoftwareProductRate(monthly_fee=Decimal('0.00')),
            ],
        }

        for product_rate in BOOTSTRAP_PRODUCT_RATES[edition]:
            if dry_run:
                logger.info("[DRY RUN] Creating Product: %s" % product)
                logger.info("[DRY RUN] Corresponding product rate of $%d created." % product_rate.monthly_fee)
            else:
                try:
                    product = self.orm.SoftwareProduct.objects.get(name=product.name)
                    if self.verbose:
                        logger.info("Product '%s' already exists. Using "
                                    "existing product to add rate."
                                    % product.name)
                except self.orm.SoftwareProduct.DoesNotExist:
                    product.save()
                    if self.verbose:
                        logger.info("Creating Product: %s" % product)
                if self.verbose:
                    logger.info("Corresponding product rate of $%d created."
                                % product_rate.monthly_fee)
            product_rate.product = product
            product_rates.append(product_rate)
        return product, product_rates

    def ensure_features(self, dry_run=False):
        """
        Ensures that all the Features necessary for the plans are created.
        """
        if self.verbose:
            logger.info('Ensuring Features')

        edition_to_features = defaultdict(list)
        for edition in self.editions:
            for feature_type in self.feature_types:
                feature = self.orm.Feature(name='%s %s' % (feature_type, edition), feature_type=feature_type)
                if edition == SoftwarePlanEdition.ENTERPRISE:
                    feature.name = "Dimagi Only %s" % feature.name
                if dry_run:
                    logger.info("[DRY RUN] Creating Feature: %s" % feature)
                else:
                    try:
                        feature = self.orm.Feature.objects.get(name=feature.name)
                        if self.verbose:
                            logger.info("Feature '%s' already exists. Using "
                                        "existing feature to add rate."
                                        % feature.name)
                    except ObjectDoesNotExist:
                        feature.save()
                        if self.verbose:
                            logger.info("Creating Feature: %s" % feature)
                edition_to_features[edition].append(feature)
        return edition_to_features

    def ensure_feature_rates(self, features, edition, dry_run=False):
        """
        Ensures that all the FeatureRates necessary for the plans are created.
        """
        if self.verbose:
            logger.info('Ensuring Feature Rates')

        feature_rates = []
        BOOTSTRAP_FEATURE_RATES = {
            SoftwarePlanEdition.COMMUNITY: {
                FeatureType.USER: self.orm.FeatureRate(monthly_limit=2 if self.for_tests else 50,
                                              per_excess_fee=Decimal('1.00')),
                FeatureType.SMS: self.orm.FeatureRate(monthly_limit=0),  # use defaults here
            },
            SoftwarePlanEdition.STANDARD: {
                FeatureType.USER: self.orm.FeatureRate(monthly_limit=4 if self.for_tests else 100,
                                              per_excess_fee=Decimal('1.00')),
                FeatureType.SMS: self.orm.FeatureRate(monthly_limit=3 if self.for_tests else 100),
            },
            SoftwarePlanEdition.PRO: {
                FeatureType.USER: self.orm.FeatureRate(monthly_limit=6 if self.for_tests else 500,
                                              per_excess_fee=Decimal('1.00')),
                FeatureType.SMS: self.orm.FeatureRate(monthly_limit=5 if self.for_tests else 500),
            },
            SoftwarePlanEdition.ADVANCED: {
                FeatureType.USER: self.orm.FeatureRate(monthly_limit=8 if self.for_tests else 1000,
                                              per_excess_fee=Decimal('1.00')),
                FeatureType.SMS: self.orm.FeatureRate(monthly_limit=7 if self.for_tests else 1000),
            },
            SoftwarePlanEdition.ENTERPRISE: {
                FeatureType.USER: self.orm.FeatureRate(monthly_limit=-1, per_excess_fee=Decimal('0.00')),
                FeatureType.SMS: self.orm.FeatureRate(monthly_limit=-1),
            },
        }
        for feature in features:
            feature_rate = BOOTSTRAP_FEATURE_RATES[edition][feature.feature_type]
            feature_rate.feature = feature
            if dry_run:
                logger.info("[DRY RUN] Creating rate for feature '%s': %s" % (feature.name, feature_rate))
            elif self.verbose:
                logger.info("Creating rate for feature '%s': %s" % (feature.name, feature_rate))
            feature_rates.append(feature_rate)
        return feature_rates

    BOOTSTRAP_EDITION_TO_ROLE = {
        SoftwarePlanEdition.COMMUNITY: 'community_plan_v0',
        SoftwarePlanEdition.STANDARD: 'standard_plan_v0',
        SoftwarePlanEdition.PRO: 'pro_plan_v0',
        SoftwarePlanEdition.ADVANCED: 'advanced_plan_v0',
        SoftwarePlanEdition.ENTERPRISE: 'enterprise_plan_v0',
    }
