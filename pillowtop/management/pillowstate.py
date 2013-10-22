from corehq.elastic import get_es
from pillowtop.listener import AliasedElasticPillow


def get_pillow_states(pillows):
    aliased_pillows = filter(lambda x: isinstance(x, AliasedElasticPillow), pillows)
    #make tuples of (index, alias)
    #this maybe problematic in the future if we have multiple pillows pointing to the same alias or indices
    master_aliases = dict((x.es_index, x.es_alias) for x in aliased_pillows)
    print master_aliases

    es = get_es()
    system_status = es.get('_status')
    indices = system_status['indices'].keys()
    print ""
    print "\tActive indices on ES"
    for index in indices:
        print "\t\t%s" % index
    print ""

    active_aliases = es.get('_aliases')

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

    return mapped_masters, unmapped_masters, stale_indices
