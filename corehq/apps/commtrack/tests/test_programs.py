from corehq.apps.commtrack.tests.util import CommTrackTest
from corehq.apps.commtrack.models import Program, Product
from corehq.apps.commtrack.util import make_program


class ProgramsTest(CommTrackTest):
    def setUp(self):
        super(ProgramsTest, self).setUp()
        self.new_program = make_program(
            self.domain.name,
            'new program',
            'newprogram'
        )

        self.default_program = Program.by_domain(self.domain.name, wrap=True)[0]

    def test_defaults(self):
        self.assertTrue(self.default_program.default)
        self.assertFalse(self.new_program.default)

        self.default_program.archive()
        self.assertFalse(self.default_program.is_archived)

    def test_archive(self):
        # assign some product to the new program
        self.products[0].program_id = self.new_program._id
        self.products[0].save()

        # make sure start state is okay
        self.assertEqual(
            2,
            len(Program.by_domain(self.domain.name))
        )
        self.assertEqual(
            0,
            len(Program.archived_by_domain(self.domain.name))
        )
        self.assertEqual(
            2,
            Product.by_program_id(self.domain.name, self.default_program._id).count()
        )
        self.assertEqual(
            1,
            Product.by_program_id(self.domain.name, self.new_program._id).count()
        )

        self.new_program.archive()

        self.assertTrue(self.new_program.is_archived)

        self.assertEqual(
            1,
            len(Program.by_domain(self.domain.name))
        )
        self.assertEqual(
            1,
            len(Program.archived_by_domain(self.domain.name))
        )
        self.assertEqual(
            3,
            Product.by_program_id(self.domain.name, self.default_program._id).count()
        )
        self.assertEqual(
            0,
            Product.by_program_id(self.domain.name, self.new_program._id).count()
        )
