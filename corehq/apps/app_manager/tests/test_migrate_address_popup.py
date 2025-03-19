from django.test import SimpleTestCase

from corehq.apps.app_manager.management.commands.migrate_address_popup import Command


def make_column(col_id="1", col_format="plain"):
    return {
        "id": col_id,
        "format": col_format
    }


plain_column = make_column()
other_column = make_column(col_id="3")
address_popup_column = make_column("2", "address-popup")


def make_app(short_columns=[], long_columns=[]):
    return {
        "modules": [
            {
                "case_details": {
                    "short": {
                        "columns": short_columns
                    },
                    "long": {
                        "columns": long_columns
                    }
                },
                "custom_variables_dict": {}
            }
        ]
    }


class CaseListCustomVariablesTests(SimpleTestCase):

    def test_migrate_app_impl(self):
        app = make_app(
            short_columns=[
                make_column(),
                address_popup_column
            ]
        )

        migrated_app = Command.migrate_app_impl(app, False)
        self.assertIsNotNone(migrated_app)
        self.assertEqual(
            migrated_app,
            make_app(
                short_columns=[plain_column],
                long_columns=[address_popup_column]
            )
        )

    def test_migrate_app_impl_already_migrated(self):
        app = make_app(
            short_columns=[plain_column],
            long_columns=[address_popup_column]
        )

        migrated_app = Command.migrate_app_impl(app, False)
        self.assertIsNone(migrated_app)
        self.assertEqual(
            app,
            make_app(
                short_columns=[plain_column],
                long_columns=[address_popup_column]
            )
        )

    def test_migrate_app_impl_no_change(self):
        app = make_app()
        migrated_app = Command.migrate_app_impl(app, False)
        self.assertIsNone(migrated_app)

    def test_migrate_app_impl_reverse(self):
        app = make_app(
            short_columns=[
                plain_column
            ],
            long_columns=[
                other_column,
                address_popup_column
            ]
        )

        migrated_app = Command.migrate_app_impl(app, True)
        self.assertIsNotNone(migrated_app)
        self.assertEqual(
            migrated_app,
            make_app(
                short_columns=[
                    plain_column,
                    address_popup_column
                ],
                long_columns=[
                    other_column,
                ]
            )
        )
