from __future__ import absolute_import
from __future__ import unicode_literals
from unittest import TestCase
from django.template import Context, Template, TemplateSyntaxError


class TestCaseTag(TestCase):

    def test_basic_case(self):
        self.assertEqual(render("""
            {% case place "first" %}
                You are first!
            {% endcase %}
        """, place="first"), "You are first!")

    def test_second_case(self):
        self.assertEqual(render("""
            {% case place "first" %}
                You won first place!
            {% case "second" %}
                Second place!
            {% endcase %}
        """, place="second"), "Second place!")

    def test_missing_case_without_else(self):
        self.assertEqual(render("""
            {% case place "first" %}one{% endcase %}
        """, place="nope"), "")

    def test_else(self):
        self.assertEqual(render("""
            {% case place "first" %}
                You won first place!
            {% case "second" %}
                Second place!
            {% else %}
                Practice is the way to success.
            {% endcase %}
        """, place="third"), "Practice is the way to success.")

    def test_multi_value_initial_case(self):
        temp = Template("""
            {% load hq_shared_tags %}
            {% case val 1 2 %}hit{% endcase %}
        """)
        self.assertEqual(render(temp, val=1), "hit")
        self.assertEqual(render(temp, val=2), "hit")

    def test_multi_value_inner_case(self):
        temp = Template("""
            {% load hq_shared_tags %}
            {% case val 1 %}one{% case 2 3 %}two{% endcase %}
        """)
        self.assertEqual(render(temp, val=2), "two")
        self.assertEqual(render(temp, val=3), "two")

    def test_duplicate_case(self):
        with self.assertRaises(TemplateSyntaxError) as context:
            render("{% case val 1 %}one{% case 1 %}other one{% endcase %}")
        self.assertEqual(str(context.exception),
            "duplicate case not allowed: 1")

    def test_too_few_initial_args(self):
        with self.assertRaises(TemplateSyntaxError) as context:
            render("{% load hq_shared_tags %}{% case place %}{% endcase %}")
        self.assertEqual(str(context.exception),
            "initial 'case' tag requires at least two arguments: a lookup "
            "expression and at least one value for the first case")

    def test_too_few_inner_args(self):
        with self.assertRaises(TemplateSyntaxError) as context:
            render("{% case place 1 %}{% case %}{% endcase %}")
        self.assertEqual(str(context.exception),
            "inner 'case' tag requires at least one argument")

    def test_initial_expression_value(self):
        with self.assertRaises(TemplateSyntaxError) as context:
            render("{% case place x %}{% endcase %}")
        self.assertEqual(str(context.exception),
            "'case' tag expected literal value, got x")

    def test_inner_expression_value(self):
        with self.assertRaises(TemplateSyntaxError) as context:
            render("{% case place 1 %}{% case x %}{% endcase %}")
        self.assertEqual(str(context.exception),
            "'case' tag expected literal value, got x")

    def test_else_with_args(self):
        with self.assertRaises(TemplateSyntaxError) as context:
            render("{% case place 1 %}{% else x %}{% endcase %}")
        self.assertEqual(str(context.exception),
            "'else' tag does not accept arguments")

    def test_endcase_with_args(self):
        with self.assertRaises(TemplateSyntaxError) as context:
            render("{% case place 1 %}{% endcase x %}")
        self.assertEqual(str(context.exception),
            "'endcase' tag does not accept arguments")


def render(template, **context):
    if not isinstance(template, Template):
        template = Template("{% load hq_shared_tags %}\n" + template)
    return template.render(Context(context)).strip()
