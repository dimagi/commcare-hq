import base64

from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from corehq.apps.domain.utils import clear_domain_names

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionAdjustment,
)
from corehq.apps.domain.models import Domain
from corehq.apps.export.models import (
    PathNode,
    ExportItem,
    FormExportInstance,
    CaseExportInstance,
    ExportColumn, TableConfiguration)
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.models import HQApiKey, WebUser


class OdataTestMixin(object):

    view_urlname = None

    @classmethod
    def _set_up_class(cls):
        cls.client = Client()
        clear_domain_names('test_domain')
        cls.domain = Domain(name='test_domain')
        cls.domain.save()
        cls.web_user = WebUser.create(cls.domain.name, 'test_user', 'my_password', None, None)
        cls._setup_user_permissions()
        cls.app_id = '1234'
        cls.instance = cls.get_instance(cls.domain.name)
        cls.instance.save()

    @classmethod
    def get_instance(cls, domain_name):
        raise NotImplementedError()

    @classmethod
    def _teardownclass(cls):
        cls.domain.delete()

    @classmethod
    def _setup_accounting(cls):
        call_command('cchq_prbac_bootstrap')
        cls.account, _ = BillingAccount.get_or_create_account_by_domain(cls.domain.name, created_by='')
        plan_version = DefaultProductPlan.get_default_plan_version(SoftwarePlanEdition.ADVANCED)
        cls.subscription = Subscription.new_domain_subscription(cls.account, cls.domain.name, plan_version)

    @classmethod
    def _teardown_accounting(cls):
        SubscriptionAdjustment.objects.all().delete()
        cls.subscription.delete()
        cls.account.delete()

    @classmethod
    def _setup_user_permissions(cls):
        cls.web_user.set_role(cls.domain.name, 'admin')
        cls.web_user.save()

    def _execute_query(self, credentials, view_url=None):
        return self.client.get(view_url or self.view_url, HTTP_AUTHORIZATION='Basic ' + credentials)

    @classmethod
    def _get_correct_credentials(cls):
        return OdataTestMixin._get_basic_credentials(cls.web_user.username, 'my_password')

    @staticmethod
    def _get_basic_credentials(username, password):
        return base64.b64encode("{}:{}".format(username, password).encode('utf-8')).decode('utf-8')

    @property
    def view_url(self):
        return reverse(self.view_urlname, kwargs={
            'domain': self.domain.name, 'config_id': self.instance._id, 'api_version': 'v1'})


@es_test
class CaseOdataTestMixin(OdataTestMixin):

    @classmethod
    def get_instance(cls, domain_name):
        return CaseExportInstance(
            domain=domain_name,
            is_odata_config=True,
            transform_dates=False,
            tables=[
                TableConfiguration(
                    selected=True,
                    columns=[
                        ExportColumn(label='closed', selected=True,
                                     # this is what exports generate for a base level property
                                     item=ExportItem(
                                         path=[PathNode(name='closed')])),
                        ExportColumn(label='date_modified', selected=True,
                                     item=ExportItem(path=[
                                         PathNode(name='date_modified')])),
                        ExportColumn(label='selected_property_1',
                                     selected=True),
                        ExportColumn(label='selected_property_2',
                                     selected=True),
                        ExportColumn(label='unselected_property'),
                    ],
                ),
            ]
        )


@es_test
class FormOdataTestMixin(OdataTestMixin):

    @classmethod
    def get_instance(cls, domain_name):
        return FormExportInstance(
            domain=domain_name,
            is_odata_config=True,
            transform_dates=False,
            tables=[
                TableConfiguration(
                    selected=True,
                    columns=[
                        ExportColumn(label='received_on', selected=True,
                                     item=ExportItem(
                                         path=[PathNode(name='received_on')])),
                        ExportColumn(label='started_time', selected=True,
                                     item=ExportItem(path=[
                                         PathNode(name='form'),
                                         PathNode(name='meta'),
                                         PathNode(name='timeStart'),
                                     ])),

                        ExportColumn(label='selected_property_1',
                                     selected=True),
                        ExportColumn(label='selected_property_2',
                                     selected=True),
                        ExportColumn(label='unselected_property'),
                    ],
                ),
            ]
        )


def generate_api_key_from_web_user(web_user):
    api_key = HQApiKey.objects.get_or_create(user=web_user.get_django_user())[0]
    api_key.key = api_key.generate_key()
    api_key.save()
    return api_key
