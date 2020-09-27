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
            couch_submodel = doc.get(spec['couch_attr'], {})
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
                "wrap": cls._wrap_stock_levels_config,
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
                del doc['force_to_consumption_case_types']
        return doc

    @classmethod
    def _wrap_stock_levels_config(cls, doc):
        for attr in ['emergency_level', 'understock_threshold', 'overstock_threshold']:
            if attr in doc:
                doc[attr] = round(float(doc[attr], 8))
        return doc

    @classmethod
    def _wrap_action_config(cls, data):
        if 'action_type' in data:
            data['action'] = data['action_type']
            del data['action_type']
        if 'name' in data:
            if data['name'] == 'lost':
                data['subaction'] = 'loss'
            del data['name']
        return data

    def update_or_create_sql_object(self, doc):
        # This method uses a try/catch instead of update_or_create so that it can use sync_To_couch=False
        # for the saves while avoiding the bug described in https://github.com/dimagi/commcare-hq/pull/28001
        # CommtrackConfig documents aren't created often, so the risk of a race condition is low.
        try:
            model = self.sql_class().objects.get(couch_id=doc['_id'])
            created = False
        except ObjectDoesNotExist:
            model = self.sql_class()(couch_id=doc['_id'])
            created = True
        for attr in self.attrs_to_sync():
            value = doc.get(attr)
            if value is not None:
                setattr(model, attr, value)

        for spec in self.one_to_one_submodels():
            couch_submodel = doc.get(spec['couch_attr'])
            sql_name = spec['sql_class'].__name__.lower()
            if 'wrap' in spec:
                couch_submodel = spec['wrap'](couch_submodel)
            try:
                sql_submodel = getattr(model, sql_name)
            except ObjectDoesNotExist:
                sql_submodel = spec['sql_class']()
            for field in spec['fields']:
                value = couch_submodel.get(field)
                if value is not None:
                    setattr(sql_submodel, field, couch_submodel.get(field))
            setattr(model, sql_name, sql_submodel)

        # Make sure model has id so that submodels can be saved
        if created:
            model.save(sync_to_couch=False)

        for spec in self.one_to_one_submodels():
            submodel = getattr(model, spec['sql_class'].__name__.lower())
            submodel.commtrack_config = model
            submodel.save()

        sql_actions = []
        for a in doc['actions']:
            a = self._wrap_action_config(a)
            sql_actions.append(SQLActionConfig(
                action=a.get('action'),
                subaction=a.get('subaction'),
                _keyword=a.get('_keyword'),
                caption=a.get('caption'),
            ))
        model.set_actions(sql_actions)
        model.save(sync_to_couch=False)

        return (model, created)
