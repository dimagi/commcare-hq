from __future__ import absolute_import
from corehq.toggles import all_toggles


def find_static_toggle(slug):
    for toggle in all_toggles():
        if toggle.slug == slug:
            return toggle
