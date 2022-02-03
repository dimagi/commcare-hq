from django.utils.translation import ugettext_lazy as _

from memoized import memoized

from dimagi.ext.couchdbkit import DictProperty

from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.specs import EvaluationContext, FactoryContext
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.repeaters.expression.repeater_generators import (
    ExpressionPayloadGenerator,
)
from corehq.motech.repeaters.models import Repeater
from corehq.toggles import EXPRESSION_REPEATER


class BaseExpressionRepeater(Repeater):
    """Uses a UCR dict expression to send a generic json response
    """
    class Meta:
        app_label = 'repeaters'

    configured_filter = DictProperty()
    configured_expression = DictProperty()
    payload_generator_classes = (ExpressionPayloadGenerator,)

    @property
    @memoized
    def parsed_filter(self):
        return FilterFactory.from_spec(self.configured_filter, FactoryContext.empty())

    @property
    @memoized
    def parsed_expression(self):
        return ExpressionFactory.from_spec(self.configured_expression, FactoryContext.empty())

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


class CaseExpressionRepeater(BaseExpressionRepeater):
    friendly_name = _("Configurable Case Repeater")

    @memoized
    def payload_doc(self, repeat_record):
        return CaseAccessors(repeat_record.domain).get_case(repeat_record.payload_id).to_json()
