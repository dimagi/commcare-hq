from corehq.apps.commtrack.tests.util import CommTrackTest
from corehq.apps.programs.models import Program
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.commtrack.util import make_program
from couchdbkit import ResourceNotFound


class ProgramsTest(CommTrackTest):
    def setUp(self):
        super(ProgramsTest, self).setUp()
        self.default_program = Program.by_domain(self.domain.name, wrap=True).one()
        self.new_program = make_program(
            self.domain.name,
            'new program',
            'newprogram'
        )

    def test_defaults(self):
        self.assertTrue(self.default_program.default)
        self.assertFalse(self.new_program.default)

        with self.assertRaises(Exception) as context:
            self.default_program.delete()

        self.assertEqual(context.exception.message, 'You cannot delete the default program')

    def test_delete(self):
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
            SQLProduct.objects.get(product_id=self.products[0]._id).program_id
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
            Product.get(self.products[0]._id).program_id
        )
        self.assertEqual(
            self.default_program._id,
            SQLProduct.objects.get(product_id=self.products[0]._id).program_id
        )
