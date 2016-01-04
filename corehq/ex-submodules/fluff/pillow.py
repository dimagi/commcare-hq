from couchdbkit import ResourceNotFound
from dimagi.utils.read_only import ReadOnlyObject
from pillowtop.checkpoints.manager import get_default_django_checkpoint_for_legacy_pillow_class
from pillowtop.listener import PythonPillow, PYTHONPILLOW_CHUNK_SIZE
from .indicators import IndicatorDocument
from .signals import BACKEND_SQL, BACKEND_COUCH, indicator_document_updated


class FluffPillow(PythonPillow):
    document_filter = None
    wrapper = None
    indicator_class = IndicatorDocument
    domains = None
    doc_type = None
    save_direct_to_sql = False
    delete_filtered = False  # delete docs not matching filter

    # see explanation in IndicatorDocument for how this is used
    deleted_types = ()

    def __init__(self, chunk_size=None, checkpoint=None, change_feed=None, preload_docs=True):
        # explicitly check against None since we want to pass chunk_size=0 through
        chunk_size = chunk_size if chunk_size is not None else PYTHONPILLOW_CHUNK_SIZE
        # fluff pillows should default to SQL checkpoints
        checkpoint = checkpoint or get_default_django_checkpoint_for_legacy_pillow_class(self.__class__)
        super(FluffPillow, self).__init__(
            chunk_size=chunk_size,
            checkpoint=checkpoint,
            change_feed=change_feed,
            preload_docs=preload_docs,
        )

    @classmethod
    def get_sql_engine(cls):
        engine = getattr(cls, '_engine', None)
        if not engine:
            import sqlalchemy
            from django.conf import settings
            engine = sqlalchemy.create_engine(settings.SQL_REPORTING_DATABASE_URL)
            cls._engine = engine
        return engine

    def python_filter(self, change):
        self._assert_pillow_valid()

        def domain_filter(domain):
            return domain in self.domains

        def doc_type_filter(doc_type):
            return self._is_doc_type_match(doc_type) or self._is_doc_type_deleted_match(doc_type)

        # if metadata.domain is specified this should never have to get the document out of the DB
        domain = change.metadata.domain if change.metadata else change.get_document().get('domain')
        if domain_filter(domain):
            # same for metadata.document_type
            doc_type = (change.metadata and change.metadata.document_type) or change.get_document().get('doc_type')
            return doc_type_filter(doc_type)

    def _assert_pillow_valid(self):
        assert self.domains
        assert None not in self.domains
        assert self.doc_type is not None
        assert self.doc_type not in self.deleted_types

    @classmethod
    def _get_base_name(cls):
        # used in the name/checkpoint ID
        return 'fluff'

    def _is_doc_type_match(self, type):
        return type == self.doc_type

    def _is_doc_type_deleted_match(self, type):
        return type in self.deleted_types

    def change_transform(self, doc_dict):
        delete = False
        doc = self.wrapper.wrap(doc_dict)
        doc = ReadOnlyObject(doc)

        if self.document_filter and not self.document_filter.filter(doc):
            if self.delete_filtered:
                delete = True
            else:
                return None

        indicator = _get_indicator_doc_from_class_and_id(self.indicator_class, doc.get_id)
        if not self._is_doc_type_deleted_match(doc.doc_type):
            indicator.calculate(doc)
        else:
            indicator['id'] = doc.get_id
            delete = True

        return {
            'doc_dict': doc_dict,
            'indicators': indicator,
            'delete': delete
        }

    def change_transport(self, data):
        indicators = data['indicators']

        diff = indicators.diff(None)  # pass in None for old_doc to force diff with ALL indicators
        if self.save_direct_to_sql:
            engine = self.get_sql_engine()
            if not data['delete']:
                indicators.save_to_sql(diff, engine)
            else:
                indicators.delete_from_sql(engine)
            engine.dispose()
        else:
            if not data['delete']:
                indicators.save()
            else:
                indicators.delete()


        backend = BACKEND_SQL if self.save_direct_to_sql else BACKEND_COUCH
        indicator_document_updated.send(
            sender=self,
            doc=data['doc_dict'],
            diff=diff,
            backend=backend
        )


def _get_indicator_doc_from_class_and_id(indicator_class, doc_id):
    indicator_id = '%s-%s' % (indicator_class.__name__, doc_id)
    try:
        return indicator_class.get(indicator_id)
    except ResourceNotFound:
        return indicator_class(_id=indicator_id)
