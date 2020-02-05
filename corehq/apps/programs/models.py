from datetime import datetime

from django.db import models
from django.utils.translation import ugettext as _

from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateTimeProperty,
    Document,
    StringProperty,
)

from corehq.apps.groups.models import dt_no_Z_re
from corehq.apps.products.models import Product, SQLProduct


class SQLProgram(models.Model):
    domain = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=255)
    last_modified = models.DateTimeField()
    default = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    couch_id = models.CharField(max_length=126, null=True, db_index=True)

    class Meta:
        db_table = "programs_program"


class Program(Document):
    """
    A program, e.g. "hiv" or "tb"
    """
    domain = StringProperty()
    name = StringProperty()
    code = StringProperty()
    last_modified = DateTimeProperty()
    default = BooleanProperty(default=False)
    is_archived = BooleanProperty(default=False)

    @classmethod
    def wrap(cls, data):
        # If "Z" is missing because of the Aug 2014 migration, then add it.
        # cf. Group class
        last_modified = data.get('last_modified')
        if last_modified and dt_no_Z_re.match(last_modified):
            data['last_modified'] += 'Z'
        return super(Program, cls).wrap(data)

    def save(self, *args, **kwargs):
        self.last_modified = datetime.utcnow()
        super(Program, self).save(*args, **kwargs)
        self.clear_caches(self.domain)

    @classmethod
    def by_domain(cls, domain):
        """
        Gets all programs in a domain.
        """
        kwargs = dict(
            view_name='program_by_code/view',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True
        )
        return Program.view(**kwargs)

    @classmethod
    def default_for_domain(cls, domain):
        programs = cls.by_domain(domain)
        for p in programs:
            if p.default:
                return p

    def delete(self):
        # you cannot delete the default program
        if self.default:
            raise Exception(_('You cannot delete the default program'))

        default = Program.default_for_domain(self.domain)

        sql_products = SQLProduct.objects.filter(domain=self.domain,
                                                 program_id=self.get_id)
        to_save = []
        for product in sql_products.couch_products():
            product['program_id'] = default._id
            to_save.append(product)

            # break up saving in case there are many products
            if len(to_save) > 500:
                Product.bulk_save(to_save)
                to_save = []

        Product.bulk_save(to_save)

        # bulk update sqlproducts
        sql_products.update(program_id=default._id)

        super(Program, self).delete()
        self.clear_caches(self.domain)

    def unarchive(self):
        """
        Unarchive a program, causing it (and its data) to show
        up in Couch and SQL views again.
        """
        self.is_archived = False
        self.save()

    def get_products_count(self):
        return (SQLProduct.objects
                .filter(domain=self.domain, program_id=self.get_id)
                .count())

    @classmethod
    def clear_caches(cls, domain):
        from casexml.apps.phone.utils import clear_fixture_cache
        from corehq.apps.programs.fixtures import PROGRAM_FIXTURE_BUCKET
        clear_fixture_cache(domain, PROGRAM_FIXTURE_BUCKET)
