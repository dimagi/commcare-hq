from django.db import transaction

from memoized import memoized

from dimagi.utils.logging import notify_exception

from corehq.util.soft_assert import soft_assert
from corehq.util.test_utils import unit_testing_only
from corehq.util.view_utils import absolute_reverse

skipped_destructive_rebuild_assert = soft_assert(exponential_backoff=False)


class IndicatorAdapter(object):
    def __init__(self, config):
        self.config = config

    @memoized
    def get_table(self):
        raise NotImplementedError

    def rebuild_table(self, initiated_by=None, source=None, skip_log=False, diffs=None):
        raise NotImplementedError

    def drop_table(self, initiated_by=None, source=None, skip_log=False):
        raise NotImplementedError

    @unit_testing_only
    def clear_table(self):
        raise NotImplementedError

    def get_query_object(self):
        raise NotImplementedError

    def best_effort_save(self, doc, eval_context=None):
        """
        Does a best-effort save of the document. Will fail silently if the save is not successful.

        For certain known, expected errors this will do no additional logging.
        For unexpected errors it will log them.
        """
        try:
            indicator_rows = self.get_all_values(doc, eval_context)
        except Exception as e:
            self.handle_exception(doc, e)
        else:
            self._best_effort_save_rows(indicator_rows, doc)

    def _best_effort_save_rows(self, rows, doc):
        """
        Like save rows, but should catch errors and log them
        """
        raise NotImplementedError

    def handle_exception(self, doc, exception):
        from corehq.util.cache_utils import is_rate_limited
        ex_clss = exception.__class__
        key = '{domain}.{table}.{ex_mod}.{ex_name}'.format(
            domain=self.config.domain,
            table=self.config.table_id,
            ex_mod=ex_clss.__module__,
            ex_name=ex_clss.__name__
        )
        if not is_rate_limited(key):
            notify_exception(
                None,
                'unexpected error saving UCR doc',
                details={
                    'domain': self.config.domain,
                    'doc_id': doc.get('_id', '<unknown>'),
                    'table': '{} ({})'.format(self.config.display_name, self.config._id)
                }
            )

    def save(self, doc, eval_context=None):
        """
        Saves the document. Should bubble up known errors.
        """
        indicator_rows = self.get_all_values(doc, eval_context)
        self.save_rows(indicator_rows)

    def save_rows(self, rows, use_shard_col=True):
        raise NotImplementedError

    def bulk_save(self, docs):
        """
        Evalutes UCR rows for given docs and saves the result in bulk.
        """
        raise NotImplementedError

    def get_all_values(self, doc, eval_context=None):
        "Gets all the values from a document to save"
        return self.config.get_all_values(doc, eval_context)

    def bulk_delete(self, docs, use_shard_col=True):
        for doc in docs:
            self.delete(doc, use_shard_col)

    def delete(self, doc, use_shard_col=True):
        raise NotImplementedError

    @property
    def run_asynchronous(self):
        return self.config.asynchronous

    def get_distinct_values(self, column, limit):
        raise NotImplementedError

    def log_table_build(self, initiated_by, source):
        from corehq.apps.userreports.models import DataSourceActionLog
        self._log_action(initiated_by, source, DataSourceActionLog.BUILD)

    def log_table_rebuild(self, initiated_by, source, skip=False, diffs=None):
        from corehq.apps.userreports.models import DataSourceActionLog
        self._log_action(initiated_by, source, DataSourceActionLog.REBUILD, skip=skip, diffs=diffs)

    def log_table_rebuild_skipped(self, source, diffs):
        from corehq.apps.userreports.models import DataSourceActionLog
        self._log_action(None, source, DataSourceActionLog.REBUILD, diffs=diffs, skip_destructive=True)

    def log_table_drop(self, initiated_by, source, skip=False):
        from corehq.apps.userreports.models import DataSourceActionLog
        self._log_action(initiated_by, source, DataSourceActionLog.DROP, skip=skip)

    def log_table_migrate(self, source, diffs, initiated_by=None):
        from corehq.apps.userreports.models import DataSourceActionLog
        self._log_action(initiated_by, source, DataSourceActionLog.MIGRATE, diffs=diffs)

    def _log_action(self, initiated_by, source, action, diffs=None, skip_destructive=False, skip=False):
        """
        :param initiated_by: Username of initiating user
        :param source: Source of action
        :param action: Action being performed. See ``DataSourceActionLog.action`` for options.
        :param diffs: Migration diff dict
        :param skip_destructive: True if this action was not actually performed because the data source
                                 is marked with ``disable_destructive_rebuild``
        :param skip: If True the action will not be logged.
        """
        from corehq.apps.userreports.models import DataSourceActionLog
        if skip or not self.config.data_source_id:
            return

        kwargs = {
            'domain': self.config.domain,
            'indicator_config_id': self.config.data_source_id,
            'action': action,
            'initiated_by': initiated_by,
            'action_source': source,
            'migration_diffs': diffs,
            'skip_destructive': skip_destructive,
        }

        try:
            # make this atomic so that errors don't affect outer transactions
            with transaction.atomic():
                log = DataSourceActionLog.objects.create(**kwargs)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:  # noqa
            # catchall to make sure errors here don't interfere with real workflows
            notify_exception(None, "Error saving UCR action log", details=kwargs)
        else:
            skipped_destructive_rebuild_assert(not skip_destructive, "Destructive UCR action skipped", {
                'indicator_config_id': self.config.data_source_id,
                'action': action,
                'action_log_url': absolute_reverse('admin:userreports_datasourceactionlog_change', args=(log.id,))
            })


class IndicatorAdapterLoadTracker(object):
    def __init__(self, adapter, track_load):
        self.adapter = adapter
        self._track_load = track_load

    def __getattr__(self, attr):
        return getattr(self.adapter, attr)

    def track_load(self, value=1):
        self._track_load(value)

    def save_rows(self, rows, use_shard_col=True):
        self._track_load(len(rows))
        self.adapter.save_rows(rows, use_shard_col)

    def delete(self, doc, use_shard_col=True):
        self._track_load()
        self.adapter.delete(doc, use_shard_col)

    def get_distinct_values(self, column, limit):
        distinct_values, too_many_values = self.adapter.get_distinct_values(column, limit)
        self._track_load(len(distinct_values))
        return distinct_values, too_many_values
