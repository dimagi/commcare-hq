import json
from string import Formatter

from django.core.serializers.json import DjangoJSONEncoder
from corehq import toggles
from corehq.apps.userreports.const import UCR_NAMED_EXPRESSION
from corehq.apps.userreports.models import UCRExpression

from corehq.apps.userreports.specs import EvaluationContext
from corehq.motech.repeaters.repeater_generators import BasePayloadGenerator


class ExpressionPayloadGenerator(BasePayloadGenerator):
    @property
    def content_type(self):
        return 'application/json'

    def get_payload(self, repeat_record, payload_doc, parsed_expression):
        result = parsed_expression(payload_doc, EvaluationContext(payload_doc))
        return json.dumps(result, cls=DjangoJSONEncoder)

    def get_url(self, repeat_record, url_template, payload_doc):
        if not toggles.UCR_EXPRESSION_REGISTRY.enabled(repeat_record.domain):
            return ""

        required_template_vars = [fn for _, fn, _, _ in Formatter().parse(url_template) if fn is not None]
        context = EvaluationContext(payload_doc)
        expressions = {
            expression.name: expression.wrapped_definition(context)
            for expression in UCRExpression.objects.filter(
                domain=repeat_record.domain,
                name__in=required_template_vars,
                expression_type=UCR_NAMED_EXPRESSION,
            )
        }
        return url_template.format(
            **{
                template_var: expressions[template_var](payload_doc) if template_var in expressions else ""
                for template_var in required_template_vars
            }
        )
