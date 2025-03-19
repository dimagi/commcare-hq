from django.core.management import BaseCommand
from memoized import memoized

from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = "Detects and removes duplicate domains"

    def add_arguments(self, parser):
        parser.add_argument('--selection-method', choices=['default', 'smart'], default='default', help="""
        'default' selects the domain doc currently given by Domain.get_by_name.
        'smart' uses additional signals to attempt to determine the best domain doc.
        Note that this may be different from the one currently given by Domain.get_by_name,
        and thus this will result in a change in the domain doc actively used by the system.
        """)
        parser.add_argument('--dry-run', action='store_true', default=False)

    def handle(self, selection_method, dry_run, **options):
        domains = Domain.get_all()
        seen = set([])
        dups = set([])
        for domain in domains:
            if domain.name in seen:
                dups.add(domain.name)
            else:
                seen.add(domain.name)

        if not dups:
            self.stdout.write('Found no duplicate domains')

        for domain in sorted(dups):
            currently_chosen_domain_doc = Domain.get_by_name(domain)
            all_domain_docs = Domain.view(
                "domain/domains",
                key=domain,
                reduce=False,
                include_docs=True,
            ).all()

            if selection_method == 'default':
                chosen_domain_doc = currently_chosen_domain_doc
            elif selection_method == 'smart':
                chosen_domain_doc = sorted(
                    all_domain_docs,
                    key=lambda d: score_domain_doc(
                        d,
                        is_currently_chosen=(d.get_id == currently_chosen_domain_doc.get_id)
                    )
                )[-1]
            else:
                raise NotImplementedError()

            other_domain_docs = [d for d in all_domain_docs if d.get_id != chosen_domain_doc.get_id]

            self.stdout.write(f'Found duplicate docs for domain: {domain}')
            self.stdout.write(
                f'Chosen\t'
                f'{"_id":32}\t'
                f'{"name":16}\t'
                f'is_active\t'
                f'{"date_created":26}\t'
                f'{"_rev":32}\t'
                f'score'
            )

            for domain_doc in all_domain_docs:
                chosen = domain_doc._id == chosen_domain_doc._id
                chosen_str = '-->' if chosen else ''
                self.stdout.write(
                    f'{chosen_str}\t'
                    f'{domain_doc._id}\t'
                    f'{domain_doc.name:16}\t'
                    f'{str(domain_doc.is_active):9}\t'
                    f'{domain_doc.date_created}\t'
                    f'{domain_doc._rev}\t'
                    f'{score_domain_doc(domain_doc, is_currently_chosen=chosen):.2f}'
                )

            if not dry_run:
                self.stdout.write('')
                self.stdout.write(f'{chosen_domain_doc._id} chosen')
                for dom in other_domain_docs:
                    self.stdout.write(f'{dom._id} ...', ending='')
                    dom.doc_type = 'Domain-DUPLICATE'
                    dom.save()
                    self.stdout.write(' archived')


@memoized
def score_domain_doc(domain_doc, *, is_currently_chosen):
    """
    Score a domain doc's worthiness as the "real" domain doc

    The score is based on three factors:
    - Is it the one that is currently returned by Domain.get_by_name?
      This is a strong prior, since it's what is currently being served
    - Has the doc been updated many times?
      This could mean that somehow in the past it was being treated as the real doc, even if not presently
    - Is the domain active? If only one of the many domain docs is active, we probably want that one
    """
    score = 0
    if is_currently_chosen:
        score += 2
    if domain_doc.is_active:
        score += 3
    # add to the score the square root of the number of times the doc has been updated (since initial creation)
    # and give this just a tad more importance so that a rev of 5 beats being currently chosen
    rev_count = float(domain_doc._rev.split('-')[0])
    score += ((rev_count - 1) ** .5) * 1.01
    return score / 5
