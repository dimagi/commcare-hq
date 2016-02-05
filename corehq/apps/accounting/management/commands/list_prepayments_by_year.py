from datetime import date
from django.core.management import BaseCommand

from corehq.apps.accounting.models import (
    CreditAdjustment,
    CreditAdjustmentReason,
)


def _make_value_safe_for_csv(value):
    return unicode(value).replace('\n', '\\n').replace(',', ';').replace('\t', '\\t').replace('\r', '\\r')


def _get_subscription_from_credit_adj(credit_adj):
    return credit_adj.credit_line.subscription or (
        credit_adj.invoice.subscription if credit_adj.invoice else None
    )


def _domain_from_adjustment(credit_adj):
    subscription = _get_subscription_from_credit_adj(credit_adj)
    if subscription:
        return subscription.subscriber.domain
    else:
        return credit_adj.credit_line.account.created_by_domain


class Command(BaseCommand):
    help = 'Print to the console a CSV of credit adjustment info for the given year.'

    def handle(self, year, *args, **options):
        print 'Note,Project Space,Web User,Date Created,Amount,Subscription Type,ID in database'

        year = int(year)
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        for credit_adj in CreditAdjustment.objects.filter(
            date_created__gte=start,
            date_created__lte=end
        ).filter(
            reason=CreditAdjustmentReason.MANUAL,
        ).exclude(
            web_user__isnull=True
        ).exclude(
            web_user=''
        ):
            related_subscription = _get_subscription_from_credit_adj(credit_adj)
            print u','.join(map(
                _make_value_safe_for_csv,
                [
                    credit_adj.note,
                    _domain_from_adjustment(credit_adj),
                    credit_adj.web_user,
                    credit_adj.date_created,
                    credit_adj.amount,
                    related_subscription.service_type if related_subscription else 'account-level_adjustment',
                    credit_adj.id,
                ]
            ))
