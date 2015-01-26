import dateutil
from couchdbkit import ResourceNotFound
from couchdbkit.ext.django.loading import get_db
import pytz
from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance


class IndicatorDocument(object):

    def is_update(self, doc_dict):
        """Checks to see whether doc_dict shows an update from the current
        instance doc, so that we keep things in sync.
        """
        raise NotImplementedError("is_update must be implemented")

    @classmethod
    def get_db(cls):
        """Makes damn sure that we get the correct DB for this particular app"""
        app_label = getattr(cls._meta, "app_label")
        db = get_db(app_label)
        cls._db = db
        return db

    @classmethod
    def get_or_create_from_dict(cls, doc_dict):
        if '_rev' in doc_dict:
            del doc_dict['_rev']
        if '_attachments' in doc_dict:
            doc_dict['_attachments'] = {}

        try:
            existing_doc = cls.get_db().get(doc_dict['_id'])
            is_existing = True
            doc_instance = cls.wrap(existing_doc)
            if doc_instance.is_update(doc_dict):
                doc_instance._doc.update(doc_dict)
                doc_instance.save()
        except ResourceNotFound:
            doc_instance = cls.wrap(doc_dict)
            doc_instance.save()
            is_existing = False

        return doc_instance, is_existing


class IndicatorXForm(IndicatorDocument, XFormInstance):

    def save(self, **kwargs):
        self.doc_type = 'IndicatorXForm'
        super(IndicatorXForm, self).save(**kwargs)

    def is_update(self, doc_dict):
        # Highly unlikely that an XForm will have been updated from prod.
        return False


class IndicatorCase(IndicatorDocument, CommCareCase):

    def save(self, **kwargs):
        self.doc_type = 'IndicatorCase'
        super(IndicatorCase, self).save(**kwargs)

    def is_update(self, doc_dict):
        dict_modified_on = dateutil.parser.parse(doc_dict['modified_on'])
        current_modified_on = dateutil.parser.parse(self._doc['modified_on'])
        return current_modified_on < dict_modified_on
