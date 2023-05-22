from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.ucr_expressions import create_linked_ucr_expression, update_linked_ucr_expression
from corehq.apps.linked_domain.exceptions import DomainLinkError
from corehq.apps.userreports.const import UCR_NAMED_EXPRESSION
from corehq.apps.userreports.models import UCRExpression


class TestLinkedUCRExpressions(BaseLinkedAppsTest):
    def setUp(self):
        super(TestLinkedUCRExpressions, self).setUp()

        self.ucr_expression = UCRExpression.objects.create(
            name="ping",
            domain=self.domain_link.master_domain,
            description="Testing linked UCR Expressions",
            expression_type=UCR_NAMED_EXPRESSION,
            definition={"type": "constant", "constant": "row your boat gently downstream"},
        )

    def test_create_expression_link(self):
        new_expression_id = create_linked_ucr_expression(self.domain_link, self.ucr_expression.id)
        new_expression = UCRExpression.objects.get(id=new_expression_id)
        self.assertEqual(new_expression.definition, self.ucr_expression.definition)

    def test_create_expression_raises_error_on_name_conflict(self):
        self._create_ucr_expression(self.domain_link.linked_domain, name="ConflictingName")
        upstream_ucr = self._create_ucr_expression(self.domain_link.master_domain, name="ConflictingName")

        with self.assertRaisesMessage(DomainLinkError,
                "Expression ConflictingName already exists in the downstream domain domain-2"):
            create_linked_ucr_expression(self.domain_link, upstream_ucr.id)

    def test_update_expression_link(self):
        new_expression_id = create_linked_ucr_expression(self.domain_link, self.ucr_expression.id)
        self.ucr_expression.name = "pong"
        new_definition = {"type": "constant", "constant": "keep rowing"}
        self.ucr_expression.definition = new_definition
        self.ucr_expression.save()

        update_linked_ucr_expression(self.domain_link, new_expression_id)

        linked_ucr_expression = UCRExpression.objects.get(id=new_expression_id)
        self.assertEqual(linked_ucr_expression.name, "pong")
        self.assertEqual(linked_ucr_expression.definition, new_definition)

    def _create_ucr_expression(self, domain, name="ping", description="Test"):
        return UCRExpression.objects.create(
            name=name,
            domain=domain,
            description=description,
            expression_type=UCR_NAMED_EXPRESSION,
            definition={"type": "constant", "constant": "test constant"},
        )
