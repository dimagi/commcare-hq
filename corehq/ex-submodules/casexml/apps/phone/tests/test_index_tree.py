from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase, override_settings
from casexml.apps.phone.models import IndexTree, SimplifiedSyncLog


class TestExtendedFootprint(SimpleTestCase):

    def test_simple_linear_structure(self):
        [grandparent_id, parent_id, child_id] = all_cases = ['grandparent', 'parent', 'child']
        tree = IndexTree(indices={
            child_id: convert_list_to_dict([parent_id]),
            parent_id: convert_list_to_dict([grandparent_id]),
        })
        cases = IndexTree.get_all_dependencies(grandparent_id, tree, IndexTree())
        self.assertEqual(cases, set(all_cases))

    def test_multiple_children(self):
        [grandparent_id, parent_id, child_id_1, child_id_2] = all_cases = ['rickard', 'ned', 'bran', 'arya']
        tree = IndexTree(indices={
            child_id_1: convert_list_to_dict([parent_id]),
            child_id_2: convert_list_to_dict([parent_id]),
            parent_id: convert_list_to_dict([grandparent_id]),
        })
        cases = IndexTree.get_all_dependencies(grandparent_id, tree, IndexTree())
        self.assertEqual(cases, set(all_cases))

    def test_simple_extension(self):
        [host_id, extension_id] = all_ids = ['host', 'extension']
        extension_tree = IndexTree(indices={
            extension_id: convert_list_to_dict([host_id]),
        })
        child_tree = IndexTree()
        extension_dependencies = IndexTree.get_all_dependencies(extension_id, child_tree, extension_tree)
        self.assertEqual(extension_dependencies, set(all_ids))

    def test_extension_long_chain(self):
        [host_id, extension_id, extension_id_2, extension_id_3] = all_ids = [
            'host', 'extension', 'extension_2', 'extension_3']

        extension_tree = IndexTree(indices={
            extension_id: convert_list_to_dict([host_id]),
            extension_id_2: convert_list_to_dict([extension_id]),
            extension_id_3: convert_list_to_dict([extension_id_2]),
        })
        child_tree = IndexTree()
        extension_dependencies = IndexTree.get_all_dependencies(extension_id, child_tree, extension_tree)
        self.assertEqual(set(all_ids), extension_dependencies)
        host_dependencies = IndexTree.get_all_dependencies(host_id, child_tree, extension_tree)
        self.assertEqual(set(all_ids), host_dependencies)

    def test_child_and_extension(self):
        """
         +---+       +---+
         | C +--c--->| H |
         +-+-+       +-+-+
           ^           ^
           |e          |e
         +-+-+       +-+-+
         |E2 |       |E1 |
         +---+       +---+
        """
        [host_id, extension_id, child_id, extension_id_2] = all_ids = ['host', 'extension', 'child', 'extension_2']
        child_tree = IndexTree(indices={
            child_id: convert_list_to_dict([host_id]),
        })
        extension_tree = IndexTree(indices={
            extension_id: convert_list_to_dict([host_id]),
            extension_id_2: convert_list_to_dict([child_id]),
        })

        extension_dependencies = IndexTree.get_all_dependencies(extension_id, child_tree, extension_tree)
        self.assertEqual(set(all_ids), extension_dependencies)
        host_dependencies = IndexTree.get_all_dependencies(host_id, child_tree, extension_tree)
        self.assertEqual(set(all_ids), host_dependencies)
        child_dependencies = IndexTree.get_all_dependencies(child_id, child_tree, extension_tree)
        self.assertEqual(set([child_id, extension_id_2]), child_dependencies)

    def test_multiple_indices(self):
        """
        +---+       +---+
        | C +--c--->| H |
        +---+--e--->+-+-+
                      ^
        +---+         |
        | E +----e----+
        +---+
        """
        [host_id, extension_id, child_id] = all_ids = ['host', 'extension', 'child']
        child_tree = IndexTree(indices={
            child_id: convert_list_to_dict([host_id]),
        })
        extension_tree = IndexTree(indices={
            extension_id: convert_list_to_dict([host_id]),
            child_id: convert_list_to_dict([host_id]),
        })

        child_dependencies = IndexTree.get_all_dependencies(child_id, child_tree, extension_tree)
        self.assertEqual(set(all_ids), child_dependencies)

        extension_dependencies = IndexTree.get_all_dependencies(extension_id, child_tree, extension_tree)
        self.assertEqual(set(all_ids), extension_dependencies)


class PurgingTest(SimpleTestCase):

    def test_purge_parent_then_child(self):
        [parent_id, child_id] = all_ids = ['parent', 'child']
        tree = IndexTree(indices={
            child_id: convert_list_to_dict([parent_id]),
        })
        sync_log = SimplifiedSyncLog(index_tree=tree, case_ids_on_phone=set(all_ids))
        # this has no effect
        sync_log.purge(parent_id)
        self.assertTrue(child_id in sync_log.case_ids_on_phone)
        self.assertTrue(parent_id in sync_log.case_ids_on_phone)
        self.assertFalse(child_id in sync_log.dependent_case_ids_on_phone)
        self.assertTrue(parent_id in sync_log.dependent_case_ids_on_phone)

        # this should purge it entirely
        sync_log.purge(child_id)
        self.assertFalse(child_id in sync_log.case_ids_on_phone)
        self.assertFalse(parent_id in sync_log.case_ids_on_phone)

    def test_purge_child_then_parent(self):
        [parent_id, child_id] = all_ids = ['parent', 'child']
        tree = IndexTree(indices={
            child_id: convert_list_to_dict([parent_id]),
        })
        sync_log = SimplifiedSyncLog(index_tree=tree, case_ids_on_phone=set(all_ids))

        # this should purge the child but not the parent
        sync_log.purge(child_id)
        self.assertFalse(child_id in sync_log.case_ids_on_phone)
        self.assertTrue(parent_id in sync_log.case_ids_on_phone)
        self.assertFalse(child_id in sync_log.dependent_case_ids_on_phone)
        self.assertFalse(parent_id in sync_log.dependent_case_ids_on_phone)

        # then purging the parent should purge it
        sync_log.purge(parent_id)
        self.assertFalse(parent_id in sync_log.case_ids_on_phone)
        self.assertFalse(parent_id in sync_log.dependent_case_ids_on_phone)

    def test_purge_tiered_top_down(self):
        [grandparent_id, parent_id, child_id] = all_ids = ['grandparent', 'parent', 'child']
        tree = IndexTree(indices={
            child_id: convert_list_to_dict([parent_id]),
            parent_id: convert_list_to_dict([grandparent_id]),
        })
        sync_log = SimplifiedSyncLog(index_tree=tree, case_ids_on_phone=set(all_ids))

        # this has no effect other than to move the grandparent to dependent
        sync_log.purge(grandparent_id)
        for id in all_ids:
            self.assertTrue(id in sync_log.case_ids_on_phone)

        self.assertTrue(grandparent_id in sync_log.dependent_case_ids_on_phone)
        self.assertFalse(parent_id in sync_log.dependent_case_ids_on_phone)
        self.assertFalse(child_id in sync_log.dependent_case_ids_on_phone)

        # likewise, this should have no effect other than to move the parent to dependent
        sync_log.purge(parent_id)
        for id in all_ids:
            self.assertTrue(id in sync_log.case_ids_on_phone)

        self.assertTrue(grandparent_id in sync_log.dependent_case_ids_on_phone)
        self.assertTrue(parent_id in sync_log.dependent_case_ids_on_phone)
        self.assertFalse(child_id in sync_log.dependent_case_ids_on_phone)

        # this should now purge everything
        sync_log.purge(child_id)
        for id in all_ids:
            self.assertFalse(id in sync_log.case_ids_on_phone)
            self.assertFalse(id in sync_log.dependent_case_ids_on_phone)

    def test_purge_tiered_bottom_up(self):
        [grandparent_id, parent_id, child_id] = all_ids = ['grandparent', 'parent', 'child']
        tree = IndexTree(indices={
            child_id: convert_list_to_dict([parent_id]),
            parent_id: convert_list_to_dict([grandparent_id]),
        })
        sync_log = SimplifiedSyncLog(index_tree=tree, case_ids_on_phone=set(all_ids))

        # just purging the child should purge just the child
        sync_log.purge(child_id)
        self.assertTrue(grandparent_id in sync_log.case_ids_on_phone)
        self.assertTrue(parent_id in sync_log.case_ids_on_phone)
        self.assertFalse(child_id in sync_log.case_ids_on_phone)

        # same for the parent
        sync_log.purge(parent_id)
        self.assertTrue(grandparent_id in sync_log.case_ids_on_phone)
        self.assertFalse(parent_id in sync_log.case_ids_on_phone)

        # same for the grandparentparent
        sync_log.purge(grandparent_id)
        self.assertFalse(grandparent_id in sync_log.case_ids_on_phone)

    def test_purge_multiple_children(self):
        [grandparent_id, parent_id, child_id_1, child_id_2] = all_ids = ['rickard', 'ned', 'bran', 'arya']
        tree = IndexTree(indices={
            child_id_1: convert_list_to_dict([parent_id]),
            child_id_2: convert_list_to_dict([parent_id]),
            parent_id: convert_list_to_dict([grandparent_id]),
        })
        sync_log = SimplifiedSyncLog(index_tree=tree, case_ids_on_phone=set(all_ids))

        # first purge the parent and grandparent
        sync_log.purge(grandparent_id)
        sync_log.purge(parent_id)
        self.assertTrue(grandparent_id in sync_log.case_ids_on_phone)
        self.assertTrue(grandparent_id in sync_log.dependent_case_ids_on_phone)
        self.assertTrue(parent_id in sync_log.case_ids_on_phone)
        self.assertTrue(parent_id in sync_log.dependent_case_ids_on_phone)

        # just purging one child should preserve the parent index
        sync_log.purge(child_id_1)
        self.assertTrue(grandparent_id in sync_log.case_ids_on_phone)
        self.assertTrue(grandparent_id in sync_log.dependent_case_ids_on_phone)
        self.assertTrue(parent_id in sync_log.case_ids_on_phone)
        self.assertTrue(parent_id in sync_log.dependent_case_ids_on_phone)
        self.assertFalse(child_id_1 in sync_log.case_ids_on_phone)

        # purging the other one should wipe it
        sync_log.purge(child_id_2)
        for id in all_ids:
            self.assertFalse(id in sync_log.case_ids_on_phone)
            self.assertFalse(id in sync_log.dependent_case_ids_on_phone)

    @override_settings(DEBUG=True)
    def test_purge_partial_children(self):
        [parent_id, child_id_1, child_id_2] = all_ids = ['parent', 'child1', 'child2']
        tree = IndexTree(indices={
            child_id_1: convert_list_to_dict([parent_id]),
            child_id_2: convert_list_to_dict([parent_id]),
        })
        sync_log = SimplifiedSyncLog(
            index_tree=tree,
            case_ids_on_phone=set(all_ids),
            dependent_case_ids_on_phone=set([parent_id, child_id_2])
        )
        # this used to fail with an AssertionError
        sync_log.purge(parent_id)

    def test_purge_multiple_parents(self):
        [grandparent_id, mother_id, father_id, child_id] = all_ids = ['heart-tree', 'catelyn', 'ned', 'arya']
        tree = IndexTree(indices={
            child_id: convert_list_to_dict([mother_id, father_id]),
            mother_id: convert_list_to_dict([grandparent_id]),
            father_id: convert_list_to_dict([grandparent_id]),
        })
        sync_log = SimplifiedSyncLog(index_tree=tree, case_ids_on_phone=set(all_ids))

        # first purge everything but the child
        sync_log.purge(grandparent_id)
        sync_log.purge(mother_id)
        sync_log.purge(father_id)

        # everything should still be relevant because of the child
        for id in all_ids:
            self.assertTrue(id in sync_log.case_ids_on_phone)

        # purging the child should wipe everything else
        sync_log.purge(child_id)
        for id in all_ids:
            self.assertFalse(id in sync_log.case_ids_on_phone)
            self.assertFalse(id in sync_log.dependent_case_ids_on_phone)

    def test_purge_circular_loops(self):
        [peer_id_1, peer_id_2] = all_ids = ['jaime', 'cersei']
        tree = IndexTree(indices={
            peer_id_1: convert_list_to_dict([peer_id_2]),
            peer_id_2: convert_list_to_dict([peer_id_1]),
        })
        sync_log = SimplifiedSyncLog(index_tree=tree, case_ids_on_phone=set(all_ids))

        # purging one peer should keep everything around
        sync_log.purge(peer_id_1)
        for id in all_ids:
            self.assertTrue(id in sync_log.case_ids_on_phone)

        # purging the second peer should remove everything
        sync_log.purge(peer_id_2)
        for id in all_ids:
            self.assertFalse(id in sync_log.case_ids_on_phone)

    def test_purge_very_circular_loops(self):
        [peer_id_1, peer_id_2, peer_id_3] = all_ids = ['drogon', 'rhaegal', 'viserion']
        tree = IndexTree(indices={
            peer_id_1: convert_list_to_dict([peer_id_2]),
            peer_id_2: convert_list_to_dict([peer_id_3]),
            peer_id_3: convert_list_to_dict([peer_id_1]),
        })
        sync_log = SimplifiedSyncLog(index_tree=tree, case_ids_on_phone=set(all_ids))

        # purging the first two, should still keep everything around
        sync_log.purge(peer_id_1)
        sync_log.purge(peer_id_2)
        for id in all_ids:
            self.assertTrue(id in sync_log.case_ids_on_phone)

        sync_log.purge(peer_id_3)
        for id in all_ids:
            self.assertFalse(id in sync_log.case_ids_on_phone)

    def test_purge_self_indexing(self):
        [id] = ['recursive']
        tree = IndexTree(indices={
            id: convert_list_to_dict([id]),
        })
        sync_log = SimplifiedSyncLog(index_tree=tree, case_ids_on_phone=set([id]))
        sync_log.purge(id)
        self.assertFalse(id in sync_log.case_ids_on_phone)
        self.assertFalse(id in sync_log.dependent_case_ids_on_phone)


class ExtensionCasesPurgingTest(SimpleTestCase):

    def test_purge_host(self, ):
        """Purging host removes the extension
        """
        [host_id, extension_id] = all_ids = ['host', 'extension']
        extension_tree = IndexTree(indices={
            extension_id: convert_list_to_dict([host_id]),
        })
        sync_log = SimplifiedSyncLog(extension_index_tree=extension_tree,
                                     dependent_case_ids_on_phone=set([extension_id]),
                                     case_ids_on_phone=set(all_ids))

        sync_log.purge(host_id)
        self.assertFalse(extension_id in sync_log.case_ids_on_phone)
        self.assertFalse(host_id in sync_log.case_ids_on_phone)

    def test_purge_extension(self, ):
        """Purging extension removes host
        """
        [host_id, extension_id] = all_ids = ['host', 'extension']
        extension_tree = IndexTree(indices={
            extension_id: convert_list_to_dict([host_id]),
        })
        sync_log = SimplifiedSyncLog(extension_index_tree=extension_tree,
                                     dependent_case_ids_on_phone=set([host_id]),
                                     case_ids_on_phone=set(all_ids))

        sync_log.purge(extension_id)
        self.assertFalse(extension_id in sync_log.case_ids_on_phone)
        self.assertFalse(host_id in sync_log.case_ids_on_phone)

    def test_purge_host_extension_has_extension(self):
        """Purging host when extension has an extension removes both
        """
        [host_id, extension_id, extension_extension_id] = all_ids = ['host', 'extension', 'extension_extension']
        extension_tree = IndexTree(indices={
            extension_id: convert_list_to_dict([host_id]),
            extension_extension_id: convert_list_to_dict([extension_id]),
        })
        sync_log = SimplifiedSyncLog(extension_index_tree=extension_tree,
                                     dependent_case_ids_on_phone=set([extension_id, extension_extension_id]),
                                     case_ids_on_phone=set(all_ids))
        sync_log.purge(host_id)
        self.assertFalse(extension_id in sync_log.case_ids_on_phone)
        self.assertFalse(extension_extension_id in sync_log.case_ids_on_phone)
        self.assertFalse(host_id in sync_log.case_ids_on_phone)

    def test_purge_host_has_multiple_extensions(self):
        """Purging host with multiple extensions should remove all extensions
        """
        [host_id, extension_id, extension_id_2] = all_ids = ['host', 'extension', 'extension_2']
        extension_tree = IndexTree(indices={
            extension_id: convert_list_to_dict([host_id]),
            extension_id_2: convert_list_to_dict([host_id]),
        })
        sync_log = SimplifiedSyncLog(extension_index_tree=extension_tree,
                                     dependent_case_ids_on_phone=set([extension_id, extension_id_2]),
                                     case_ids_on_phone=set(all_ids))
        sync_log.purge(host_id)
        self.assertFalse(extension_id in sync_log.case_ids_on_phone)
        self.assertFalse(extension_id_2 in sync_log.case_ids_on_phone)
        self.assertFalse(host_id in sync_log.case_ids_on_phone)

    def test_purge_extension_host_has_multiple_extensions(self):
        """Purging an extension should remove host and its other extensions
        """
        [host_id, extension_id, extension_id_2] = all_ids = ['host', 'extension', 'extension_2']
        extension_tree = IndexTree(indices={
            extension_id: convert_list_to_dict([host_id]),
            extension_id_2: convert_list_to_dict([host_id]),
        })
        sync_log = SimplifiedSyncLog(extension_index_tree=extension_tree,
                                     dependent_case_ids_on_phone=set([host_id, extension_id_2]),
                                     case_ids_on_phone=set(all_ids))
        sync_log.purge(extension_id)
        self.assertFalse(extension_id in sync_log.case_ids_on_phone)
        self.assertFalse(extension_id_2 in sync_log.case_ids_on_phone)
        self.assertFalse(host_id in sync_log.case_ids_on_phone)

    def test_purge_extension_non_dependent_host(self):
        """Purging an extension should not remove the host or itself if the host is directly owned
        """
        [host_id, extension_id] = all_ids = ['host', 'extension']
        extension_tree = IndexTree(indices={
            extension_id: convert_list_to_dict([host_id]),
        })
        sync_log = SimplifiedSyncLog(extension_index_tree=extension_tree,
                                     case_ids_on_phone=set(all_ids))
        sync_log.purge(extension_id)
        self.assertTrue(extension_id in sync_log.case_ids_on_phone)
        self.assertTrue(host_id in sync_log.case_ids_on_phone)

    def test_purge_child_of_extension(self):
        """Purging child of extension should remove extension and host
        """
        [host_id, extension_id, child_id] = all_ids = ['host', 'extension', 'child']
        child_tree = IndexTree(indices={
            child_id: convert_list_to_dict([extension_id]),
        })
        extension_tree = IndexTree(indices={
            extension_id: convert_list_to_dict([host_id]),
        })
        sync_log = SimplifiedSyncLog(extension_index_tree=extension_tree,
                                     index_tree=child_tree,
                                     dependent_case_ids_on_phone=set([host_id, extension_id]),
                                     case_ids_on_phone=set(all_ids))

        sync_log.purge(child_id)
        self.assertFalse(extension_id in sync_log.case_ids_on_phone)
        self.assertFalse(child_id in sync_log.case_ids_on_phone)
        self.assertFalse(host_id in sync_log.case_ids_on_phone)

    def test_purge_extension_host_is_parent(self):
        """Purging an extension should not purge the host or the extension if the host is a depenency for a child
        """
        [host_id, extension_id, child_id] = all_ids = ['host', 'extension', 'child']
        child_tree = IndexTree(indices={
            child_id: convert_list_to_dict([host_id]),
        })
        extension_tree = IndexTree(indices={
            extension_id: convert_list_to_dict([host_id]),
        })
        sync_log = SimplifiedSyncLog(extension_index_tree=extension_tree,
                                     index_tree=child_tree,
                                     dependent_case_ids_on_phone=set([host_id]),
                                     case_ids_on_phone=set(all_ids))

        sync_log.purge(extension_id)
        self.assertTrue(extension_id in sync_log.case_ids_on_phone)
        self.assertTrue(child_id in sync_log.case_ids_on_phone)
        self.assertTrue(host_id in sync_log.case_ids_on_phone)

    def test_open_extension_of_extension(self):
        all_ids = ['host', 'extension', 'extension_of_extension']
        host_id, extension_id, extension_of_extension_id = all_ids
        extension_tree = IndexTree(indices={
            extension_id: convert_list_to_dict([host_id]),
            extension_of_extension_id: convert_list_to_dict([extension_id]),
        })
        sync_log = SimplifiedSyncLog(extension_index_tree=extension_tree,
                                     dependent_case_ids_on_phone=set([host_id, extension_id]),
                                     closed_cases=set([host_id, extension_id]),
                                     case_ids_on_phone=set(all_ids))

        sync_log.purge(host_id)
        self.assertFalse(host_id in sync_log.case_ids_on_phone)
        self.assertFalse(extension_id in sync_log.case_ids_on_phone)
        self.assertFalse(extension_of_extension_id in sync_log.case_ids_on_phone)

    def test_open_child_of_extension(self):
        [host_id, extension_id, child_of_extension_id] = all_ids = ['host', 'extension', 'child_of_extension']
        extension_tree = IndexTree(indices={
            extension_id: convert_list_to_dict([host_id]),

        })
        child_tree = IndexTree(indices={
            child_of_extension_id: convert_list_to_dict([extension_id]),
        })
        sync_log = SimplifiedSyncLog(extension_index_tree=extension_tree,
                                     index_tree=child_tree,
                                     dependent_case_ids_on_phone=set([host_id, extension_id]),
                                     closed_cases=set([host_id, extension_id]),
                                     case_ids_on_phone=set(all_ids))

        for case_id in [host_id, extension_id]:
            sync_log.purge(case_id)
            self.assertTrue(host_id in sync_log.case_ids_on_phone)
            self.assertTrue(extension_id in sync_log.case_ids_on_phone)
            self.assertTrue(child_of_extension_id in sync_log.case_ids_on_phone)


def convert_list_to_dict(a_list):
    return {str(i): item for i, item in enumerate(a_list)}
