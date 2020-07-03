from django.core.management.base import BaseCommand
from django.db import connections


def get_sequences(cursor):
    cursor.execute("SELECT c.relname FROM pg_class c WHERE c.relkind = 'S';")
    return [r for (r, ) in cursor.fetchall()]


def get_last_values(sequences, cursor):
    # list of sequences
    select_statements = [
        '(SELECT last_value FROM {})'.format(s)
        for s in sequences
    ]
    query = " UNION ALL ".join(select_statements)
    cursor.execute(query)
    result = [r for (r,) in cursor.fetchall()]
    result = dict(zip(sequences, result))
    return result


class Command(BaseCommand):
    help = """List last-value of all postgresql sequences. Useful to know
           if any primary keys are near their max limit
           """

    def add_arguments(self, parser):
        parser.add_argument(
            'dbname',
            help='Django db alias'
        )
        parser.add_argument(
            '--minval',
            type=int,
            dest='minval',
            help='print only tables where the max value is more than this provided minvalue'
        )

    def handle(self, **options):
        dbname = options['dbname']
        minval = options['minval']
        cursor = connections[dbname].cursor()
        sequences = get_sequences(cursor)
        result = get_last_values(sequences, cursor)
        print('sequence_name, last_value')
        for sequence, last_value in result.items():
            if last_value and last_value > minval:
                print(sequence, ", ", last_value)
