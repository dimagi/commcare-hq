from datetime import date

from django.core.management import BaseCommand

from corehq.apps.accounting.models import (
    CreditAdjustment,
    CreditAdjustmentReason,
)


def _make_value_safe_for_csv(value):
    return str(value).replace('\n', '\\n').replace(',', ';').replace('\t', '\\t').replace('\r', '\\r')


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

    def add_arguments(self, parser):
        parser.add_argument('year', nargs='?', type=int)

    def handle(self, year, **options):
        print('Note,Project Space,Web User,Date Created,Amount,Subscription Type,ID in database')

        credit_adjs = CreditAdjustment.objects.filter(
            reason=CreditAdjustmentReason.MANUAL,
        ).exclude(
            web_user__isnull=True
        ).exclude(
            web_user=''
        )

        if year is not None:
            credit_adjs = credit_adjs.filter(
                date_created__year=year,
            )

        for credit_adj in credit_adjs:
            related_subscription = _get_subscription_from_credit_adj(credit_adj)
            print(','.join(map(
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
            )))
