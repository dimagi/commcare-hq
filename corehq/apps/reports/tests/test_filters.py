from django.test import SimpleTestCase
from corehq.apps.reports.filters.api import paginate_options


class TestEmwfPagination(SimpleTestCase):
    def make_data_source(self, options):
        def matching_objects(query):
            if not query:
                return options
            return [o for o in options if query.lower() in o.lower()]

        def get_size(query):
            return len(matching_objects(query))

        def get_objects(query, start, size):
            return matching_objects(query)[start:start+size]

        return (get_size, get_objects)

    @property
    def data_sources(self):
        return [
            self.make_data_source(["Iron Maiden", "Van Halen", "Queen"]),
            self.make_data_source(["Oslo", "Baldwin", "Perth", "Quito"]),
            self.make_data_source([]),
            self.make_data_source(["Jdoe", "Rumpelstiltskin"]),
        ]

    def test_first_page(self):
        self.assertEqual(
            paginate_options(self.data_sources, "", 0, 5),
            ["Iron Maiden", "Van Halen", "Queen", "Oslo", "Baldwin"],
        )

    def test_second_page(self):
        self.assertEqual(
            paginate_options(self.data_sources, "", 5, 10),
            ["Perth", "Quito", "Jdoe", "Rumpelstiltskin"],
        )

    def test_query_first_page(self):
        query = "o"
        self.assertEqual(
            paginate_options(self.data_sources, query, 0, 5),
            ["Iron Maiden", "Oslo", "Quito", "Jdoe"],
        )

    def test_query_no_matches(self):
        query = "Waldo"
        self.assertEqual(
            paginate_options(self.data_sources, query, 0, 5),
            [],
        )
