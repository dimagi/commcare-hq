import json
from couchdbkit import ResourceNotFound
from django.utils.translation import ugettext_lazy as _
from corehq.apps.accounting.utils import fmt_dollar_amount, log_accounting_error
from corehq.apps.hqwebapp.async_handler import BaseAsyncHandler
from corehq.apps.hqwebapp.encoders import LazyEncoder
from corehq.apps.sms.models import INCOMING, OUTGOING, SQLMobileBackend
from corehq.apps.sms.util import get_backend_by_class_name
from corehq.apps.smsbillables.exceptions import SMSRateCalculatorError
from corehq.apps.smsbillables.models import SmsGatewayFeeCriteria, SmsGatewayFee, SmsUsageFee
from corehq.apps.smsbillables.utils import country_name_from_isd_code_or_empty
from corehq.util.quickcache import quickcache


NONMATCHING_COUNTRY = 'nonmatching'


class SMSRatesAsyncHandler(BaseAsyncHandler):
    slug = 'sms_get_rate'
    allowed_actions = [
        'get_rate'
    ]

    @property
    def get_rate_response(self):
        gateway = self.data.get('gateway')
        try:
            backend_api_id = SQLMobileBackend.get_backend_api_id(gateway, is_couch_id=True)
        except Exception as e:
            log_accounting_error(
                "Failed to get backend for calculating an sms rate due to: %s"
                % e
            )
            raise SMSRateCalculatorError("Could not obtain connection information.")

        country_code = self.data.get('country_code')
        if country_code == NONMATCHING_COUNTRY:
            country_code = None
        direction = self.data.get('direction')

        gateway_fee = SmsGatewayFee.get_by_criteria(
            backend_api_id, direction, backend_instance=gateway,
            country_code=country_code,
        )
        usage_fee = SmsUsageFee.get_by_criteria(direction, self.request.domain)
        usd_gateway_fee = gateway_fee.amount / gateway_fee.currency.rate_to_default
        usd_total = usage_fee.amount + usd_gateway_fee

        return {
            'rate': _("%s per 160 character SMS") % fmt_dollar_amount(usd_total),
        }

class SMSRatesSelect2AsyncHandler(BaseAsyncHandler):
    slug = 'sms_rate_calc'
    allowed_actions = [
        'country_code',
    ]

    @property
    def country_code_response(self):
        gateway = self.data.get('gateway')
        try:
            backend_api_id = SQLMobileBackend.get_backend_api_id(gateway, is_couch_id=True)
        except Exception:
            return []
        direction = self.data.get('direction')
        criteria_query = SmsGatewayFeeCriteria.objects.filter(
            direction=direction, backend_api_id=backend_api_id
        )
        country_codes = criteria_query.exclude(
            country_code__exact=None
        ).values_list('country_code', flat=True).distinct()
        final_codes = []
        for code in country_codes:
            country_name = country_name_from_isd_code_or_empty(code)
            final_codes.append((code, country_name))

        search_term = self.data.get('searchString')
        if search_term:
            search_term = search_term.lower().replace('+', '')
            final_codes = filter(
                lambda x: (str(x[0]).startswith(search_term)
                           or x[1].lower().startswith(search_term)),
                final_codes
            )
        final_codes = [(c[0], "+%s%s" % (c[0], " (%s)" % c[1] if c[1] else '')) for c in final_codes]
        if criteria_query.filter(country_code__exact=None).exists():
            final_codes.append((
                NONMATCHING_COUNTRY,
                _('Any Country (Delivery not guaranteed via connection)')
            ))
        return final_codes

    def _fmt_success(self, response):
        success = json.dumps({
            'results': [{
                'id': r[0],
                'text': r[1],
            } for r in response]
        }, cls=LazyEncoder)
        return success


class PublicSMSRatesAsyncHandler(BaseAsyncHandler):
    slug = 'public_sms_rate_calc'
    allowed_actions = 'public_rate'

    @property
    def public_rate_response(self):
        return self.get_rate_table(self.data.get('country_code'))

    @quickcache(['country_code'], timeout=24 * 60 * 60)
    def get_rate_table(self, country_code):
        backends = SQLMobileBackend.get_global_backends(SQLMobileBackend.SMS)

        def _directed_fee(direction, backend_api_id, backend_instance_id):
            gateway_fee = SmsGatewayFee.get_by_criteria(
                backend_api_id,
                direction,
                backend_instance=backend_instance_id,
                country_code=country_code
            )
            if not gateway_fee:
                return None
            usd_gateway_fee = gateway_fee.amount / gateway_fee.currency.rate_to_default
            usage_fee = SmsUsageFee.get_by_criteria(direction)
            return fmt_dollar_amount(usage_fee.amount + usd_gateway_fee)

        rate_table = []

        from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend

        for backend_instance in backends:
            # Skip Testing backends
            if isinstance(backend_instance, SQLTestSMSBackend):
                continue

            # skip if country is not in supported countries
            if backend_instance.supported_countries:
                if ('*' not in backend_instance.supported_countries and
                   str(country_code) not in backend_instance.supported_countries):
                    continue

            gateway_fee_incoming = _directed_fee(
                INCOMING,
                backend_instance.hq_api_id,
                backend_instance.couch_id
            )
            gateway_fee_outgoing = _directed_fee(
                OUTGOING,
                backend_instance.hq_api_id,
                backend_instance.couch_id
            )

            if gateway_fee_outgoing or gateway_fee_incoming:
                rate_table.append({
                    'gateway': backend_instance.display_name,
                    'inn': gateway_fee_incoming or 'NA',  # 'in' is reserved
                    'out': gateway_fee_outgoing or 'NA'
                })
        return rate_table
