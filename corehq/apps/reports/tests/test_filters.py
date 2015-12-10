from django.test import SimpleTestCase
from corehq.apps.reports.filters.api import paginate_options
from corehq.apps.reports.filters.forms import FormsByApplicationFilterParams, FormsByApplicationFilter, \
    PARAM_SLUG_STATUS, PARAM_VALUE_STATUS_ACTIVE, PARAM_VALUE_STATUS_DELETED, PARAM_SLUG_APP_ID, PARAM_SLUG_MODULE


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
        count, options = paginate_options(self.data_sources, "", 0, 5)
        self.assertEqual(count, 9)
        self.assertEqual(
            options,
            ["Iron Maiden", "Van Halen", "Queen", "Oslo", "Baldwin"],
        )

    def test_second_page(self):
        count, options = paginate_options(self.data_sources, "", 5, 10)
        self.assertEqual(count, 9)
        self.assertEqual(
            options,
            ["Perth", "Quito", "Jdoe", "Rumpelstiltskin"],
        )

    def test_query_first_page(self):
        query = "o"
        count, options = paginate_options(self.data_sources, query, 0, 5)
        self.assertEqual(count, 4)
        self.assertEqual(options, ["Iron Maiden", "Oslo", "Quito", "Jdoe"])

    def test_query_no_matches(self):
        query = "Waldo"
        count, options = paginate_options(self.data_sources, query, 0, 5)
        self.assertEqual(count, 0)
        self.assertEqual(options, [])


class TestFormsByApplicationFilter(SimpleTestCase):
    DOMAIN = 'test-domain'

    def _run_test(self, expected_prefix, expected_keys, input_filter_params):
        parsed = FormsByApplicationFilterParams(input_filter_params)
        prefix, keys = FormsByApplicationFilter.get_prefix_and_key_for_filter_results_and_parsed_params(
            self.DOMAIN, input_filter_params, parsed
        )
        self.assertEqual(expected_prefix, prefix)
        self.assertEqual(expected_keys, keys)

    @staticmethod
    def _make_filter(slug, value):
        return {'slug': slug, 'value': value}

    def test_prefix_and_keys_none(self):
        self._run_test('app module form', [self.DOMAIN], [])

    def test_prefix_and_keys_status(self):
        self._run_test('status app module form', [self.DOMAIN, PARAM_VALUE_STATUS_ACTIVE],
                       [self._make_filter(PARAM_SLUG_STATUS, PARAM_VALUE_STATUS_ACTIVE)])
        self._run_test('status app module form', [self.DOMAIN, PARAM_VALUE_STATUS_DELETED],
                       [self._make_filter(PARAM_SLUG_STATUS, PARAM_VALUE_STATUS_DELETED)])

    def test_prefix_and_keys_app_id(self):
        app_id = 'test-app-id'
        params = [
            self._make_filter(PARAM_SLUG_STATUS, PARAM_VALUE_STATUS_ACTIVE),
            self._make_filter(PARAM_SLUG_APP_ID, app_id)
        ]
        self._run_test('status app module form', [self.DOMAIN, PARAM_VALUE_STATUS_ACTIVE, app_id], params)

    def test_prefix_and_keys_module(self):
        app_id = 'test-app-id'
        params = [
            self._make_filter(PARAM_SLUG_STATUS, PARAM_VALUE_STATUS_ACTIVE),
            self._make_filter(PARAM_SLUG_APP_ID, app_id),
            self._make_filter(PARAM_SLUG_MODULE, '0'),
        ]
        self._run_test('status app module form', [self.DOMAIN, PARAM_VALUE_STATUS_ACTIVE, app_id, 0], params)

    def test_prefix_and_keys_invalid_module(self):
        app_id = 'test-app-id'
        params = [
            self._make_filter(PARAM_SLUG_STATUS, PARAM_VALUE_STATUS_ACTIVE),
            self._make_filter(PARAM_SLUG_APP_ID, app_id),
            self._make_filter(PARAM_SLUG_MODULE, 'foo'),
        ]
        self._run_test('status app module form', [self.DOMAIN, PARAM_VALUE_STATUS_ACTIVE, app_id], params)


class TestFormsByApplicationFilter(SimpleTestCase):
    DOMAIN = 'test-domain'

    def _run_test(self, expected_prefix, expected_keys, input_filter_params):
        parsed = FormsByApplicationFilterParams(input_filter_params)
        prefix, keys = FormsByApplicationFilter.get_prefix_and_key_for_parsed_params(
            self.DOMAIN, parsed
        )
        self.assertEqual(expected_prefix, prefix)
        self.assertEqual(expected_keys, keys)

    @staticmethod
    def _make_filter(slug, value):
        return {'slug': slug, 'value': value}

    def test_prefix_and_keys_none(self):
        self._run_test('app module form', [self.DOMAIN], [])

    def test_prefix_and_keys_status(self):
        self._run_test('status app module form', [self.DOMAIN, PARAM_VALUE_STATUS_ACTIVE],
                       [self._make_filter(PARAM_SLUG_STATUS, PARAM_VALUE_STATUS_ACTIVE)])
        self._run_test('status app module form', [self.DOMAIN, PARAM_VALUE_STATUS_DELETED],
                       [self._make_filter(PARAM_SLUG_STATUS, PARAM_VALUE_STATUS_DELETED)])

    def test_prefix_and_keys_app_id(self):
        app_id = 'test-app-id'
        params = [
            self._make_filter(PARAM_SLUG_STATUS, PARAM_VALUE_STATUS_ACTIVE),
            self._make_filter(PARAM_SLUG_APP_ID, app_id)
        ]
        self._run_test('status app module form', [self.DOMAIN, PARAM_VALUE_STATUS_ACTIVE, app_id], params)

    def test_prefix_and_keys_module(self):
        app_id = 'test-app-id'
        params = [
            self._make_filter(PARAM_SLUG_STATUS, PARAM_VALUE_STATUS_ACTIVE),
            self._make_filter(PARAM_SLUG_APP_ID, app_id),
            self._make_filter(PARAM_SLUG_MODULE, '0'),
        ]
        self._run_test('status app module form', [self.DOMAIN, PARAM_VALUE_STATUS_ACTIVE, app_id, 0], params)

    def test_prefix_and_keys_invalid_module(self):
        app_id = 'test-app-id'
        params = [
            self._make_filter(PARAM_SLUG_STATUS, PARAM_VALUE_STATUS_ACTIVE),
            self._make_filter(PARAM_SLUG_APP_ID, app_id),
            self._make_filter(PARAM_SLUG_MODULE, 'foo'),
        ]
        self._run_test('status app module form', [self.DOMAIN, PARAM_VALUE_STATUS_ACTIVE, app_id], params)
