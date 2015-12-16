from corehq.elastic import get_es, get_es_new
from pillowtop.listener import AliasedElasticPillow


class ElasticPillowStatus(object):

    def __init__(self, indices, mapped_masters, unmapped_masters, stale_indices):
        self.indices = indices
        self.mapped_masters = mapped_masters
        self.unmapped_masters = unmapped_masters
        self.stale_indices = stale_indices

    def dump_info(self):
        print "\n\tHQ ES Index Alias Mapping Status"
        print ""
        print "\tActive indices on ES"
        for index in self.indices:
            print "\t\t%s" % index
        print ""

        print "\t## Current ES Indices in Source Control ##"
        for m in self.mapped_masters:
            print "\t\t%s => %s [OK]" % (m[0], m[1])

        print "\t## Current ES Indices in Source Control needing preindexing ##"
        for m in self.unmapped_masters:
            print "\t\t%s != %s [Run ES Preindex]" % (m[0], m[1])

        print "\t## Stale indices on ES ##"
        for m in self.stale_indices:
            print "\t\t%s: %s" % (m[0], "Holds [%s]" % ','.join(m[1]) if len(m[1]) > 0 else "No Alias, stale")
        print "done"


def get_pillow_states(pillows):
    """
    return tuple: (mapped_masters, unmapped_masters, stale_indices)

    mapped masters: ES indices as known in the current running code state that
    correctly have the alias applied to them

    unmapped masters: ES indices as known in the current running code state
    that do not have the alias applied to them

    stale indices: ES indices running on ES that are not part of the current
    source control.

    """
    aliased_pillows = filter(lambda x: isinstance(x, AliasedElasticPillow), pillows)
    # make tuples of (index, alias)
    # this maybe problematic in the future if we have multiple pillows
    # pointing to the same alias or indices
    master_aliases = dict((x.es_index, x.es_alias) for x in aliased_pillows)

    es = get_es_new()
    active_aliases = es.indices.get_aliases()

    unseen_masters = master_aliases.keys()
    mapped_masters = []
    unmapped_masters = []
    stale_indices = []

    for idx, alias_dict in active_aliases.items():
        line = ["\t\t", idx]
        is_master = False
        if idx in master_aliases:
            is_master = True

            unseen_masters.remove(idx)

        if is_master:
            if master_aliases[idx] in alias_dict['aliases']:
                #is master, has alias, good
                mapped_masters.append((idx, master_aliases[idx]))
            else:
                #is master, but doesn't have alias, bad
                unmapped_masters.append((idx, master_aliases[idx]))
                line.append('=> Does not have alias yet :(')
        else:
            #not a master index
            stale_tuple = (idx, alias_dict['aliases'].keys())
            stale_indices.append(stale_tuple)
    unmapped_masters.extend([(x, master_aliases[x]) for x in unseen_masters])

    return ElasticPillowStatus(
        active_aliases.keys(), mapped_masters, unmapped_masters, stale_indices,
    )
