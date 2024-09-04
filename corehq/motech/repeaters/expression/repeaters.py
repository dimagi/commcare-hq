import logging
from json import JSONDecodeError

from django.utils.translation import gettext_lazy as _
from memoized import memoized

from corehq.apps.hqcase.api.updates import handle_case_update
from corehq.apps.hqcase.case_helper import UserDuck
from corehq.apps.hqcase.utils import REPEATER_RESPONSE_XMLNS
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.specs import EvaluationContext, FactoryContext
from corehq.form_processor.models import CaseTransaction, CommCareCase, XFormInstance
from corehq.motech.repeaters.expression.repeater_generators import (
    ArcGISFormExpressionPayloadGenerator,
    FormExpressionPayloadGenerator,
)
from corehq.motech.repeaters.expression.repeater_generators import (
    ExpressionPayloadGenerator,
)
from corehq.motech.repeaters.models import OptionValue, Repeater
from corehq.motech.repeaters.models import is_response, is_success_response
from corehq.toggles import ARCGIS_INTEGRATION, EXPRESSION_REPEATER
from dimagi.utils.logging import notify_exception

logger = logging.getLogger(__name__)


class BaseExpressionRepeater(Repeater):
    """Uses a UCR dict expression to send a generic json response
    """
    class Meta:
        app_label = 'repeaters'
        proxy = True

    configured_filter = OptionValue(default=dict)
    configured_expression = OptionValue(default=dict)
    url_template = OptionValue(default=None)

    case_action_filter_expression = OptionValue(default=dict)
    case_action_expression = OptionValue(default=dict)

    payload_generator_classes = (ExpressionPayloadGenerator,)

    @property
    @memoized
    def parsed_filter(self):
        return FilterFactory.from_spec(self.configured_filter, FactoryContext.empty(domain=self.domain))

    @property
    @memoized
    def parsed_expression(self):
        return ExpressionFactory.from_spec(self.configured_expression, FactoryContext.empty(domain=self.domain))

    @property
    @memoized
    def parsed_case_action_filter(self):
        return FilterFactory.from_spec(
            self.case_action_filter_expression, FactoryContext.empty(domain=self.domain)
        )

    @property
    @memoized
    def parsed_case_action_expression(self):
        return ExpressionFactory.from_spec(
            self.case_action_expression, FactoryContext.empty(domain=self.domain)
        )

    @classmethod
    def available_for_domain(cls, domain):
        return EXPRESSION_REPEATER.enabled(domain)

    def allowed_to_forward(self, payload):
        payload_json = payload.to_json()
        return self.parsed_filter(payload_json, EvaluationContext(payload_json))

    @memoized
    def get_payload(self, repeat_record):
        return self.generator.get_payload(
            repeat_record,
            self.payload_doc(repeat_record),
            self.parsed_expression,
        )

    def get_url(self, repeat_record):
        base_url = super().get_url(repeat_record)
        if self.url_template:
            return base_url + self.generator.get_url(
                repeat_record,
                self.url_template,
                self.payload_doc(repeat_record),
            )
        return base_url

    def handle_response(self, response, repeat_record):
        super().handle_response(response, repeat_record)
        if self.case_action_filter_expression and is_response(response):
            try:
                self._process_response_as_case_update(response, repeat_record)
            except Exception as e:
                notify_exception(None, "Error processing response from Repeater request", e)

    def _process_response_as_case_update(self, response, repeat_record):
        domain = repeat_record.domain
        context = get_evaluation_context(domain, repeat_record, self.payload_doc(repeat_record), response)
        if not self.parsed_case_action_filter(context.root_doc, context):
            return False

        self._perform_case_update(domain, context)
        return True

    def _perform_case_update(self, domain, context):
        data = self.parsed_case_action_expression(context.root_doc, context)
        if data:
            data = data if isinstance(data, list) else [data]
            handle_case_update(
                domain=domain,
                data=data,
                user=UserDuck('system', ''),
                device_id=self.device_id,
                is_creation=False,
                xmlns=REPEATER_RESPONSE_XMLNS,
            )

    @property
    def device_id(self):
        return f'{__name__}.{self.__class__.__name__}:{self.id}'


class CaseExpressionRepeater(BaseExpressionRepeater):

    friendly_name = _("Configurable Case Repeater")

    class Meta:
        app_label = 'repeaters'
        proxy = True

    @property
    def form_class_name(self):
        return 'CaseExpressionRepeater'

    @memoized
    def payload_doc(self, repeat_record):
        return CommCareCase.objects.get_case(repeat_record.payload_id, repeat_record.domain).to_json()

    def allowed_to_forward(self, payload):
        allowed = super().allowed_to_forward(payload)
        if allowed:
            transactions = CaseTransaction.objects.get_last_n_recent_form_transaction(payload.case_id, 2)
            # last 2 transactions were from repeater updates. This suggests a cycle.
            possible_cycle = {t.xmlns for t in transactions} == {REPEATER_RESPONSE_XMLNS}
            if possible_cycle:
                logger.warning(
                    f"Possible data forwarding loop detected for case {payload.case_id}. "
                    f"Transactions: {[t.id for t in transactions]}"
                )
                return False
            last_transaction = transactions[0] if transactions else None
            return last_transaction and not (
                # last update was from this repeater, ignore
                last_transaction.xmlns == REPEATER_RESPONSE_XMLNS
                and last_transaction.device_id == self.device_id
            )
        return False


class FormExpressionRepeater(BaseExpressionRepeater):

    friendly_name = _("Configurable Form Repeater")
    payload_generator_classes = (FormExpressionPayloadGenerator,)

    class Meta:
        app_label = 'repeaters'
        proxy = True

    @property
    def form_class_name(self):
        return 'FormExpressionRepeater'

    @memoized
    def payload_doc(self, repeat_record):
        return XFormInstance.objects.get_form(
            repeat_record.payload_id,
            repeat_record.domain,
        )


class ArcGISFormExpressionRepeater(FormExpressionRepeater):

    friendly_name = _("Configurable ArcGIS Form Repeater")
    payload_generator_classes = (ArcGISFormExpressionPayloadGenerator,)

    class Meta:
        app_label = 'repeaters'
        proxy = True

    @property
    def form_class_name(self):
        return 'ArcGISFormExpressionRepeater'

    @classmethod
    def available_for_domain(cls, domain):
        return (
            super(ArcGISFormExpressionRepeater, cls).available_for_domain(domain)
            and ARCGIS_INTEGRATION.enabled(domain)
        )


def get_evaluation_context(domain, repeat_record, payload_doc, response):
    try:
        body = response.json()
    except JSONDecodeError:
        body = response.text
    return EvaluationContext({
        'domain': domain,
        'success': is_success_response(response),
        'payload': {
            'id': repeat_record.payload_id,
            'doc': payload_doc,
        },
        'response': {
            'status_code': response.status_code,
            'headers': response.headers,
            'body': body,
        },
    })
