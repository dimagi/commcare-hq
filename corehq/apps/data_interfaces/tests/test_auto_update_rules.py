from django.test import TestCase

from field_audit.models import AuditEvent, AuditAction

from corehq.apps.data_interfaces.models import AutomaticUpdateRule


class AutomaticUpdateRuleAuditingTests(TestCase):

    def test_audited_fields_for_rule_are_audited_when_created(self):
        # create rule
        AutomaticUpdateRule.objects.create(
            domain='test',
            active=True,
            workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
        )
        audit_event = AuditEvent.objects.by_model(AutomaticUpdateRule).first()
        self.assertEqual(audit_event.delta, {'active': {'new': True}, 'deleted': {'new': False}})

    def test_active_field_for_rule_is_audited_when_updated(self):
        # create rule
        rule = AutomaticUpdateRule.objects.create(
            domain='test',
            active=True,
            workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
        )
        # update rule
        rule.active = False
        rule.save()

        audit_event = AuditEvent.objects.by_model(AutomaticUpdateRule).last()
        self.assertEqual(audit_event.delta, {'active': {'old': True, 'new': False}})

    def test_deleted_field_for_rule_is_audited_when_deleted(self):
        # create rule
        rule = AutomaticUpdateRule.objects.create(
            domain='test',
            active=True,
            workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
        )
        # delete rule
        rule.deleted = True
        rule.save()

        audit_event = AuditEvent.objects.by_model(AutomaticUpdateRule).last()
        self.assertEqual(audit_event.object_class_path, 'corehq.apps.data_interfaces.models.AutomaticUpdateRule')
        self.assertEqual(audit_event.delta, {'deleted': {'old': False, 'new': True}})

    def test_bulk_delete_is_audited(self):
        AutomaticUpdateRule.objects.create(
            domain='test',
            active=True,
            workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
        )
        AutomaticUpdateRule.objects.all().delete(audit_action=AuditAction.AUDIT)
        audit_event = AuditEvent.objects.by_model(AutomaticUpdateRule).last()
        self.assertEqual({'active': {'old': True}, 'deleted': {'old': False}}, audit_event.delta)

    def test_queryset_update_is_audited(self):
        for _ in range(2):
            AutomaticUpdateRule.objects.create(
                domain='test',
                active=True,
                workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
            )

        AutomaticUpdateRule.by_domain(
            'test', workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING
        ).update(active=False, audit_action=AuditAction.AUDIT)

        audit_events = AuditEvent.objects.by_model(AutomaticUpdateRule).filter(is_create=False)
        for event in audit_events:
            self.assertEqual({'active': {'old': True, 'new': False}}, event.delta)
