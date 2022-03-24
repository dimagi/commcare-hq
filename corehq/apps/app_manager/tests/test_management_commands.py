from django.test import SimpleTestCase

from corehq.apps.app_manager.management.commands.migrate_case_search_prompt_itemset_ids import Command
from corehq.apps.app_manager.models import (
    Application,
    BuildSpec,
    CaseSearch,
    CaseSearchProperty,
    DetailColumn,
    Itemset,
    Module,
)
from corehq.apps.app_manager.util import get_correct_app_class


class MigrateCaseSearchPromptItemsetIdsTest(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.app = Application.new_app("some-domain", "Application to Migrate")
        cls.app._id = '123'
        cls.app.build_spec = BuildSpec(version='2.53.0', build_number=1)
        cls.module = cls.app.add_module(Module.new_module("Followup", None))
        cls.module.case_type = 'case'

        cls.module.case_details.long.columns.append(
            DetailColumn.wrap(dict(
                header={"en": "name"},
                model="case",
                format="plain",
                field="whatever",
            ))
        )

        cls.module.search_config = CaseSearch()

        cls.doc = cls.app.to_json()

    def _migrate_property(self, prop):
        self.doc['modules'][0]['search_config']['properties'] = [prop.to_json()]
        app_doc = Command().migrate_app(self.doc)
        if app_doc:
            app = get_correct_app_class(app_doc).wrap(app_doc)
            return app.modules[0].search_config.properties[0].itemset

    def test_text(self):
        self.assertIsNone(self._migrate_property(CaseSearchProperty(name='name', label={'en': 'Name'})))

    def test_migrate(self):
        itemset = self._migrate_property(CaseSearchProperty(
            name='favorite_color', label={'en': 'Favorite Color'}, itemset=Itemset(
                instance_id='colors', instance_uri='jr://fixture/item-list:colors',
                nodeset="instance('colors')/colors_list/colors", label='name', sort='name', value='value',
            ),
        ))
        self.assertEqual(itemset.instance_id, "item-list:colors")
        self.assertEqual(itemset.instance_uri, "jr://fixture/item-list:colors")
        self.assertEqual(itemset.nodeset, "instance('item-list:colors')/colors_list/colors")

    def test_migrate_other_quotes(self):
        itemset = self._migrate_property(CaseSearchProperty(
            name='favorite_color', label={'en': 'Favorite Color'}, itemset=Itemset(
                instance_id='colors', instance_uri='jr://fixture/item-list:colors',
                nodeset='instance("colors")/colors_list/colors', label='name', sort='name', value='value',
            ),
        ))
        self.assertEqual(itemset.instance_id, "item-list:colors")
        self.assertEqual(itemset.instance_uri, "jr://fixture/item-list:colors")
        self.assertEqual(itemset.nodeset, 'instance("item-list:colors")/colors_list/colors')

    def test_already_migrated(self):
        self.assertIsNone(self._migrate_property(CaseSearchProperty(
            name='favorite_color', label={'en': 'Favorite Color'}, itemset=Itemset(
                instance_id='item-list:colors', instance_uri='jr://fixture/item-list:colors',
                nodeset="instance('item-list:colors')/colors_list/colors",
                label='name', sort='name', value='value',
            ),
        )))

    def test_different_instance(self):
        self.assertIsNone(self._migrate_property(CaseSearchProperty(
            name='group', label={'en': 'UserGroups'}, itemset=Itemset(
                instance_id='user-groups', instance_uri='jr://fixture/user-groups',
                nodeset="instance('user-groups')/groups", label='name', sort='name', value='value',
            ),
        )))
