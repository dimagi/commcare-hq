"""
Functions used by RunPython operations in migrations.

.. note::
   Placing them in a separate module makes it easier to import them in
   unittests.

"""
from django.db import transaction, IntegrityError

from corehq.motech.repeaters.dbaccessors import iter_repeaters
from corehq.motech.repeaters.models import RepeaterStub


def create_repeaterstubs(apps, schema_editor):
    for repeater in iter_repeaters():
        with transaction.atomic():
            try:
                RepeaterStub.objects.create(
                    domain=repeater.domain,
                    repeater_id=repeater.get_id,
                    is_paused=repeater.paused,
                )
            except IntegrityError:
                # It's faster to violate uniqueness constraint and ask
                # forgiveness than to use `.get()` or `.exists()` first.
                pass
