import dateutil
from couchdbkit import ResourceNotFound
from couchdbkit.ext.django.loading import get_db
from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance


class IndicatorDocument(object):

    def is_update(self, doc_dict):
        """Checks to see whether doc_dict shows an update from the current
        instance doc, so that we keep things in sync.
        """
        raise NotImplementedError("is_update must be implemented")

    def exists_in_database(self):
        return '_rev' in self._doc

    @classmethod
    def get_db(cls):
        """Makes damn sure that we get the correct DB for this particular app
        If cls._db has been set by a superclass, then the super method is
        going to grab the wrong db without this."""
        app_label = getattr(cls._meta, "app_label")
        db = get_db(app_label)
        cls._db = db
        return db

    @classmethod
    def wrap_for_indicator_db(cls, doc_dict):
        """
        wrap a doc that was pulled from the main db
        modifying it so that it can be saved in the indicator db

        like wrap, but also:
        - sets _rev to whatever it needs to be in order to be saved
          to the indicator db without an update conflict
        - strips _attachments and external_blobs because we don't care about
          them and having the stub in JSON without the attachment will fail

        """
        try:
            current_rev = cls.get_db().get(doc_dict['_id'])['_rev']
        except ResourceNotFound:
            del doc_dict['_rev']
        else:
            doc_dict['_rev'] = current_rev

        doc_dict.pop('_attachments', None)
        doc_dict.pop('external_blobs', None)

        return cls.wrap(doc_dict)


class IndicatorXForm(IndicatorDocument, XFormInstance):

    class Meta:
        app_label = 'mvp_docs'

    def save(self, **kwargs):
        self.doc_type = 'IndicatorXForm'
        assert self.get_db().uri != XFormInstance.get_db().uri
        super(IndicatorXForm, self).save(**kwargs)

    def is_update(self, doc_dict):
        # Highly unlikely that an XForm will have been updated from prod.
        return False


class IndicatorCase(IndicatorDocument, CommCareCase):

    class Meta:
        app_label = 'mvp_docs'

    def save(self, **kwargs):
        self.doc_type = 'IndicatorCase'
        assert self.get_db().uri != CommCareCase.get_db().uri
        super(IndicatorCase, self).save(**kwargs)

    def is_update(self, doc_dict):
        dict_modified_on = dateutil.parser.parse(doc_dict['modified_on'])
        current_modified_on = dateutil.parser.parse(self._doc['modified_on'])
        return current_modified_on < dict_modified_on
