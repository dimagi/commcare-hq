from __future__ import absolute_import
from __future__ import unicode_literals

from operator import lt, gt


def merge(generator1, generator2, key=None, reverse=False):
    """Zip two sorted generators into a sorted generator"""
    # This function can be replaced by heapq.merge in python3

    END = object()

    def comes_before(a, b):
        comp = gt if reverse else lt
        return comp(key(a) if key else a, key(b) if key else b)

    g1_item = next(generator1, END)
    g2_item = next(generator2, END)
    while True:

        # If one generator is exhausted, dump the other one
        for item, other_item, other_generator in [
            (g1_item, g2_item, generator2),
            (g2_item, g1_item, generator1),
        ]:
            if item == END:
                if other_item != END:
                    yield other_item
                    for x in other_generator:
                        yield x
                return

        if comes_before(g1_item, g2_item):
            yield g1_item
            g1_item = next(generator1, END)
        else:
            yield g2_item
            g2_item = next(generator2, END)
