from django.test import SimpleTestCase
from casexml.apps.phone.models import IndexTree


class IndexTreePruningTest(SimpleTestCase):

    def test_prune_parent_then_child(self):
        [parent_id, child_id] = ['parent', 'child']
        tree = IndexTree(live_indices={
            child_id: [parent_id],
        })
        # this has no effect
        tree.prune_case(parent_id)
        self.assertTrue(child_id in tree.live_indices)
        self.assertFalse(child_id in tree.dependent_indices)

        # this should prune it entirely
        tree.prune_case(child_id)
        self.assertFalse(child_id in tree.live_indices)
        self.assertFalse(child_id in tree.dependent_indices)

    def test_prune_child_then_parent(self):
        [parent_id, child_id] = ['parent', 'child']
        tree = IndexTree(live_indices={
            child_id: [parent_id],
        })
        # this should prune it entirely
        tree.prune_case(child_id)
        self.assertFalse(child_id in tree.live_indices)
        self.assertFalse(child_id in tree.dependent_indices)

    def test_prune_tiered_top_down(self):
        [grandparent_id, parent_id, child_id] = ['grandparent', 'parent', 'child']
        tree = IndexTree(live_indices={
            child_id: [parent_id],
            parent_id: [grandparent_id],
        })
        self.assertTrue(parent_id in tree.live_indices)
        self.assertTrue(child_id in tree.live_indices)
        self.assertFalse(parent_id in tree.dependent_indices)
        self.assertFalse(child_id in tree.dependent_indices)

        # this has no effect
        tree.prune_case(grandparent_id)
        self.assertTrue(parent_id in tree.live_indices)
        self.assertTrue(child_id in tree.live_indices)
        self.assertFalse(parent_id in tree.dependent_indices)
        self.assertFalse(child_id in tree.dependent_indices)

        # this should push the parent from live to dependent
        tree.prune_case(parent_id)
        self.assertFalse(parent_id in tree.live_indices)
        self.assertTrue(parent_id in tree.dependent_indices)
        self.assertTrue(child_id in tree.live_indices)
        self.assertFalse(child_id in tree.dependent_indices)

        # this should prune everything
        tree.prune_case(child_id)
        self.assertFalse(parent_id in tree.live_indices)
        self.assertFalse(parent_id in tree.dependent_indices)
        self.assertFalse(child_id in tree.live_indices)
        self.assertFalse(child_id in tree.dependent_indices)

    def test_prune_tiered_bottom_up(self):
        [grandparent_id, parent_id, child_id] = ['grandparent', 'parent', 'child']
        tree = IndexTree(live_indices={
            child_id: [parent_id],
            parent_id: [grandparent_id],
        })
        # just pruing the child should prune everything
        tree.prune_case(child_id)
        self.assertFalse(parent_id in tree.live_indices)
        self.assertFalse(parent_id in tree.dependent_indices)
        self.assertFalse(child_id in tree.live_indices)
        self.assertFalse(child_id in tree.dependent_indices)

    def test_prune_multiple_children(self):
        [grandparent_id, parent_id, child_id_1, child_id_2] = ['rickard', 'ned', 'bran', 'arya']
        tree = IndexTree(live_indices={
            child_id_1: [parent_id],
            child_id_2: [parent_id],
            parent_id: [grandparent_id],
        })
        # just pruning one child should preserve the parent index
        tree.prune_case(child_id_1)
        self.assertTrue(parent_id in tree.live_indices)
        self.assertFalse(parent_id in tree.dependent_indices)
        self.assertFalse(child_id_1 in tree.live_indices)
        self.assertFalse(child_id_1 in tree.dependent_indices)
        self.assertTrue(child_id_2 in tree.live_indices)
        self.assertFalse(child_id_2 in tree.dependent_indices)

        # pruning the other one should wipe it
        tree.prune_case(child_id_2)
        for id in [parent_id, child_id_1, child_id_2]:
            self.assertFalse(id in tree.live_indices)
            self.assertFalse(id in tree.dependent_indices)

    def test_prune_multiple_parents(self):
        [grandparent_id, mother_id, father_id, child_id] = ['heart-tree', 'catelyn', 'ned', 'arya']
        tree = IndexTree(live_indices={
            child_id: [mother_id, father_id],
            mother_id: [grandparent_id],
            father_id: [grandparent_id],
        })
        # pruning the child should wipe everything else
        tree.prune_case(child_id)
        for id in [mother_id, father_id, child_id]:
            self.assertFalse(id in tree.live_indices)
            self.assertFalse(id in tree.dependent_indices)

    def test_prune_circular_loops(self):
        [peer_id_1, peer_id_2] = ['jaime', 'cersei']
        tree = IndexTree(live_indices={
            peer_id_1: [peer_id_2],
            peer_id_2: [peer_id_1],
        })
        # pruning the child should wipe everything else
        tree.prune_case(peer_id_1)
        self.assertFalse(peer_id_1 in tree.live_indices)
        self.assertTrue(peer_id_1 in tree.dependent_indices)
        self.assertTrue(peer_id_2 in tree.live_indices)
        self.assertFalse(peer_id_2 in tree.dependent_indices)

        tree.prune_case(peer_id_2)
        # todo: this behavior isn't defined. not really sure whether this is right
        self.assertFalse(peer_id_1 in tree.live_indices)
        self.assertFalse(peer_id_1 in tree.dependent_indices)
        self.assertFalse(peer_id_2 in tree.live_indices)
        self.assertFalse(peer_id_2 in tree.dependent_indices)

    def test_prune_very_circular_loops(self):
        [peer_id_1, peer_id_2, peer_id_3] = ['drogon', 'rhaegal', 'viserion']
        tree = IndexTree(live_indices={
            peer_id_1: [peer_id_2],
            peer_id_2: [peer_id_3],
            peer_id_3: [peer_id_1],
        })
        # prune the first two, should still be dependent
        tree.prune_case(peer_id_1)
        tree.prune_case(peer_id_2)
        self.assertFalse(peer_id_1 in tree.live_indices)
        self.assertTrue(peer_id_1 in tree.dependent_indices)
        self.assertFalse(peer_id_2 in tree.live_indices)
        self.assertTrue(peer_id_2 in tree.dependent_indices)
        self.assertTrue(peer_id_3 in tree.live_indices)
        self.assertFalse(peer_id_3 in tree.dependent_indices)

        tree.prune_case(peer_id_3)
        for id in [peer_id_1, peer_id_2, peer_id_3]:
            self.assertFalse(id in tree.live_indices)
            self.assertFalse(id in tree.dependent_indices)

    def test_prune_self_indexing(self):
        [id] = ['recursive']
        tree = IndexTree(live_indices={
            id: [id],
        })
        tree.prune_case(id)
        self.assertFalse(id in tree.live_indices)
        self.assertFalse(id in tree.dependent_indices)
