from django.test import TestCase

from couchdbkit import ResourceNotFound

from corehq.apps.commtrack.tests.util import (
    TEST_DOMAIN,
    bootstrap_domain,
    bootstrap_products,
)
from corehq.apps.commtrack.util import make_program
from corehq.apps.products.models import SQLProduct
from corehq.apps.programs.models import Program


class ProgramsTest(TestCase):
    def test_programs(self):
        self.domain = bootstrap_domain(TEST_DOMAIN)
        self.addCleanup(self.domain.delete)
        bootstrap_products(self.domain.name)
        self.products = list(SQLProduct.active_objects.filter(domain=self.domain.name).order_by('product_id'))
        self.default_program = Program.by_domain(self.domain.name, wrap=True).one()
        self.new_program = make_program(
            self.domain.name,
            'new program',
            'newprogram'
        )
        self.assertTrue(self.default_program.default)
        self.assertFalse(self.new_program.default)

        with self.assertRaises(Exception) as context:
            self.default_program.delete()

        self.assertEqual(str(context.exception), 'You cannot delete the default program')

        # assign some product to the new program
        self.products[0].program_id = self.new_program._id
        self.products[0].save()

        # make sure start state is okay
        self.assertEqual(
            2,
            len(Program.by_domain(self.domain.name))
        )
        self.assertEqual(2, self.default_program.get_products_count())
        self.assertEqual(1, self.new_program.get_products_count())
        self.assertEqual(
            self.new_program._id,
            self.products[0].program_id
        )
        self.assertEqual(
            self.new_program._id,
            SQLProduct.objects.get(product_id=self.products[0].product_id).program_id
        )

        # stash the id before we delete
        new_program_id = self.new_program._id
        self.new_program.delete()

        with self.assertRaises(ResourceNotFound):
            Program.get(new_program_id)

        self.assertEqual(1, len(Program.by_domain(self.domain.name)))
        self.assertEqual(3, self.default_program.get_products_count())
        self.assertEqual(
            self.default_program._id,
            SQLProduct.objects.get(product_id=self.products[0].product_id).program_id
        )
