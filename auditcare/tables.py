#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from djtables import Table, Column
from djtables.column import DateColumn

class AuditLogTable(Table):
    user = Column()
    access_type = Column()
    date = DateColumn(format="H:i d/m/Y")

    class Meta:
        order_by = '-date'
