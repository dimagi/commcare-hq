from django.core.exceptions import ObjectDoesNotExist

from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand
from corehq.apps.commtrack.models import (
    SQLAlertConfig,
    SQLActionConfig,
    SQLConsumptionConfig,
    SQLStockLevelsConfig,
    SQLStockRestoreConfig,
    AlertConfig,
    ConsumptionConfig,
    StockLevelsConfig,
    StockRestoreConfig,
)


class Command(PopulateSQLCommand):
    @classmethod
    def couch_doc_type(self):
        return 'CommtrackConfig'

    @classmethod
    def sql_class(self):
        from corehq.apps.commtrack.models import SQLCommtrackConfig
        return SQLCommtrackConfig

    @classmethod
    def commit_adding_migration(cls):
        return None

    @classmethod
    def diff_couch_and_sql(cls, doc, obj):
        diffs = []
        for attr in cls.attrs_to_sync():
            diffs.append(cls.diff_attr(attr, doc, obj))
        diffs.extend(cls.diff_lists(doc.get('actions', []), obj.all_actions, [
            'action', 'subaction', '_keyword', 'caption'
        ]))
        for spec in cls.one_to_one_submodels():
            normalize = float if spec["sql_class"] == SQLStockLevelsConfig else None
            sql_submodel = getattr(obj, spec['sql_class'].__name__.lower())
            couch_submodel = doc[spec['couch_attr']]
            for attr in spec['fields']:
                diffs.append(cls.diff_attr(attr, couch_submodel, sql_submodel, normalize=normalize))
        diffs = [d for d in diffs if d]
        return "\n".join(diffs) if diffs else None

    @classmethod
    def attrs_to_sync(cls):
        return [
            "domain",
            "use_auto_emergency_levels",
            "sync_consumption_fixtures",
            "use_auto_consumption",
            "individual_consumption_defaults",
        ]

    @classmethod
    def one_to_one_submodels(cls):
        return [
            {
                "sql_class": SQLAlertConfig,
                "couch_class": AlertConfig,
                "couch_attr": "alert_config",
                "fields": ['stock_out_facilities', 'stock_out_commodities', 'stock_out_rates', 'non_report'],
            },
            {
                "sql_class": SQLConsumptionConfig,
                "couch_class": ConsumptionConfig,
                "couch_attr": "consumption_config",
                "fields": [
                    'min_transactions', 'min_window', 'optimal_window',
                    'use_supply_point_type_default_consumption', 'exclude_invalid_periods',
                ]
            },
            {
                "sql_class": SQLStockLevelsConfig,
                "couch_class": StockLevelsConfig,
                "couch_attr": "stock_levels_config",
                "fields": ['emergency_level', 'understock_threshold', 'overstock_threshold'],
            },
            {
                "sql_class": SQLStockRestoreConfig,
                "couch_class": StockRestoreConfig,
                "couch_attr": "ota_restore_config",
                "fields": [
                    'section_to_consumption_types', 'force_consumption_case_types', 'use_dynamic_product_list',
                ],
                "wrap": cls._wrap_stock_restore_config,
            },
        ]

    @classmethod
    def _wrap_stock_restore_config(cls, doc):
        if 'force_to_consumption_case_types' in doc:
            realval = doc['force_to_consumption_case_types']
            oldval = doc.get('force_consumption_case_types')
            if realval and not oldval:
                doc['force_consumption_case_types'] = realval
        return doc

    def update_or_create_sql_object(self, doc):
        try:
            model = self.sql_class().objects.get(couch_id=doc['_id'])
            created = False
        except ObjectDoesNotExist:
            model = self.sql_class()(couch_id=doc['_id'])
            created = True
        for attr in self.attrs_to_sync():
            setattr(model, attr, doc.get(attr))

        for spec in self.one_to_one_submodels():
            couch_submodel = doc.get(spec['couch_attr'])
            if 'wrap' in spec:
                couch_submodel = spec['wrap'](couch_submodel)
            setattr(model, spec['sql_class'].__name__.lower(), spec['sql_class'](**{
                field: couch_submodel.get(field)
                for field in spec['fields']
            }))

        sql_actions = []
        for a in doc['actions']:
            subaction = doc.get('subaction')
            if doc.get('name', '') == 'lost':
                subaction == 'loss'
            sql_actions.append(SQLActionConfig(
                action=doc.get('action_type', doc.get('action')),
                subaction=subaction,
                _keyword=doc.get('_keyword'),
                caption=doc.get('caption'),
            ))
        model.set_actions(sql_actions)

        model.save()
        for spec in self.one_to_one_submodels():
            submodel = getattr(model, spec['sql_class'].__name__.lower())
            submodel.commtrack_config = model
            submodel.save()
        return (model, created)
