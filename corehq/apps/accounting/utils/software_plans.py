from corehq.apps.accounting.models import Subscription


def upgrade_subscriptions_to_latest_plan_version(old_plan_version, web_user,
                                                 upgrade_note):
    subscriptions_needing_upgrade = Subscription.visible_objects.filter(
        is_active=True, plan_version=old_plan_version
    )
    new_plan_version = old_plan_version.plan.get_version()
    for subscription in subscriptions_needing_upgrade:
        subscription.change_plan(
            new_plan_version,
            note=upgrade_note,
            web_user=web_user,
            service_type=subscription.service_type,
            pro_bono_status=subscription.pro_bono_status,
            funding_source=subscription.funding_source,
            internal_change=True,
            do_not_invoice=subscription.do_not_invoice,
            no_invoice_reason=subscription.no_invoice_reason,
            do_not_email_invoice=subscription.do_not_email_invoice,
            do_not_email_reminder=subscription.do_not_email_reminder,
            auto_generate_credits=subscription.auto_generate_credits,
            skip_invoicing_if_no_feature_charges=subscription.skip_invoicing_if_no_feature_charges,
            skip_auto_downgrade=subscription.skip_auto_downgrade,
            skip_auto_downgrade_reason=subscription.skip_auto_downgrade_reason,
        )
