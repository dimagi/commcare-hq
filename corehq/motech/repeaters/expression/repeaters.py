import logging

from django.utils.translation import gettext_lazy as _

from memoized import memoized
from requests import JSONDecodeError as RequestsJSONDecodeError

from dimagi.utils.logging import notify_exception

from corehq.apps.hqcase.api.updates import handle_case_update
from corehq.apps.hqcase.case_helper import UserDuck
from corehq.apps.hqcase.utils import REPEATER_RESPONSE_XMLNS
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.specs import EvaluationContext, FactoryContext
from corehq.form_processor.models import (
    CaseTransaction,
    CommCareCase,
    XFormInstance,
)
from corehq.motech.repeater_helpers import RepeaterResponse
from corehq.motech.repeaters.expression.repeater_generators import (
    ArcGISFormExpressionPayloadGenerator,
    ExpressionPayloadGenerator,
)
from corehq.motech.repeaters.models import (
    OptionValue,
    Repeater,
    is_response,
    is_success_response,
)
from corehq.toggles import ARCGIS_INTEGRATION, EXPRESSION_REPEATER

# max number of repeater updates in a chain before we stop forwarding
MAX_REPEATER_CHAIN_LENGTH = 5

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
        if not self.configured_expression:
            return None

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
        attempt = super().handle_response(response, repeat_record)
        if self.case_action_filter_expression and is_response(response):
            try:
                message = self._process_response_as_case_update(response, repeat_record)
            except Exception as e:
                notify_exception(None, "Error processing response from Repeater request", e)
                message = "Error processing response"

            attempt.message += f"\n\n{message}"
            attempt.save()

    def _process_response_as_case_update(self, response, repeat_record):
        domain = repeat_record.domain
        context = get_evaluation_context(domain, repeat_record, self.payload_doc(repeat_record), response)
        if not self.parsed_case_action_filter(context.root_doc, context):
            return "Response did not match filter"

        form_id = self._perform_case_update(domain, context)
        return f"Response generated a form: {form_id}"

    def _perform_case_update(self, domain, context):
        data = self.parsed_case_action_expression(context.root_doc, context)
        if data:
            data = data if isinstance(data, list) else [data]
            form, _ = handle_case_update(
                domain=domain,
                data=data,
                user=UserDuck('system', ''),
                device_id=self.device_id,
                is_creation=False,
                xmlns=REPEATER_RESPONSE_XMLNS,
            )
            return form.form_id

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
        return CommCareCase.objects.get_case(repeat_record.payload_id, repeat_record.domain)

    def allowed_to_forward(self, payload):
        allowed = super().allowed_to_forward(payload)
        if not allowed:
            return False

        transactions = CaseTransaction.objects.get_last_n_recent_form_transaction(
            payload.case_id, MAX_REPEATER_CHAIN_LENGTH
        )
        for transaction in transactions:
            if transaction.xmlns != REPEATER_RESPONSE_XMLNS:
                # non-repeater update found, allow forwarding
                return True

            if transaction.device_id == self.device_id:
                # all transactions to this point have been repeater updates
                # and the last one was from this repeater, it's a cycle, don't forward
                return False

        # Allow forwarding as long as we haven't hit the max chain length
        return len(transactions) < MAX_REPEATER_CHAIN_LENGTH


class FormExpressionRepeater(BaseExpressionRepeater):

    friendly_name = _("Configurable Form Repeater")

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

    def send_request(self, repeat_record, payload):
        response = super().send_request(repeat_record, payload)
        if is_success_response(response) and 'error' in response.json():
            # It _looks_ like a success response, but it's an error. :/
            return self._error_response(response.json()['error'])
        return response

    @staticmethod
    def _error_response(error_json):
        """
        The ArcGIS API returns error responses with status code 200.

        This method extracts the details from the response JSON, and
        returns a RepeaterResponse with the error details so that the
        response will be handled correctly.

        >>> error_json = {
        ...     "code": 503,
        ...     "details": [],
        ...     "message": "An error occurred."
        ... }
        >>> resp = ArcGISFormExpressionRepeater._error_response(error_json)
        >>> resp.status_code
        503
        >>> resp.reason
        'An error occurred.'

        """
        # The ArcGIS REST API documentation does not give the error
        # response schema, so we have to guess based on what we've seen.

        # `status_code` is required for us to make decisions about the
        # repeat record.  If `error_json` does not include "code", then
        # use 500 so that the repeat record will be sent again later.
        status_code = error_json.get('code', 500)

        # `reason` is what is shown in the Repeat Records Report under
        # the "Responses" button. If `error_json` is missing "message",
        # then set a value that is more useful to users than no message.
        fallback_msg = _('[No error message given by ArcGIS]')
        reason = error_json.get('message', fallback_msg)
        if 'messageCode' in error_json:
            reason += f' ({error_json["messageCode"]})'

        return RepeaterResponse(
            status_code=status_code,
            reason=reason,
            text='\n'.join(error_json.get('details', [])),
        )


def get_evaluation_context(domain, repeat_record, payload_doc, response):
    try:
        body = response.json()
    except RequestsJSONDecodeError:
        body = response.text
    return EvaluationContext({
        'domain': domain,
        'success': is_success_response(response),
        'payload': {
            'id': repeat_record.payload_id,
            'doc': payload_doc.to_json(),
        },
        'response': {
            'status_code': response.status_code,
            'headers': response.headers,
            'body': body,
        },
    })
