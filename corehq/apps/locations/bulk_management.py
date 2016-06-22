"""
Bulk rearrange locations.

This includes support for changing location types, changing locations' parents,
deleting things, and so on.  See the spec doc for specifics:
https://docs.google.com/document/d/1gZFPP8yXjPazaJDP9EmFORi88R-jSytH6TTgMxTGQSk/
"""


def bulk_update_organization(domain, location_types, locations):
    """
    Takes the existing location types and locations on the domain and modifies
    them to produce the location_types and locations passed in.

    This is used for operations that affect a large number of locations (such
    as adding a new location type), which are challenging or impossible to do
    piecemeal.
    """
    pass
