import csv

from django.test import TestCase


class CSVTestCase(TestCase):

    def _load_csv(self, path):
        with open(path, encoding='utf-8') as f:
            csv_data = list(csv.reader(f))
            headers = csv_data[0]
            for row_count, row in enumerate(csv_data):
                csv_data[row_count] = dict(zip(headers, row))
        return csv_data[1:]

    def _fasterAssertListEqual(self, list1, list2):
        if len(list1) != len(list2):
            self.fail(f'Unequal number of entries: list1 {len(list1)}, list2 {len(list2)}')

        messages = []

        for idx in range(len(list1)):
            dict1 = list1[idx]
            dict2 = list2[idx]

            differences = set()

            for key in dict1.keys():
                if key != 'id':
                    if isinstance(dict1[key], str):
                        value1 = dict1[key]
                    elif isinstance(dict1[key], list):
                        value1 = str(dict1[key])
                    else:
                        value1 = dict1[key].decode('utf-8')
                    value1 = value1.replace('\r\n', '\n')
                    value2 = dict2.get(key, '').replace('\r\n', '\n')
                    if value1 != value2:
                        differences.add(key)

            if differences:
                if self.always_include_columns:
                    differences |= self.always_include_columns
                messages.append("""
                    Actual and expected row {} are not the same
                    Actual:   {}
                    Expected: {}
                """.format(
                    idx + 1,
                    ', '.join(['{}: {}'.format(
                        difference, str(dict1[difference])) for difference in differences]
                    ),
                    ', '.join(['{}: {}'.format(
                        difference, dict2.get(difference, '')) for difference in differences]
                    )
                ))

        if messages:
            self.fail('\n'.join(messages))
