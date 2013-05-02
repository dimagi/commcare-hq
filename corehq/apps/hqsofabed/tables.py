#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from djtables import Table, Column
from djtables.column import DateColumn

class HQFormDataTable(Table):

    # instanceID = Column()
    xmlns = Column()
    received_on = DateColumn()
    timeStart = DateColumn()
    timeEnd= DateColumn()
    userID = Column()
    username = Column()
    
    class Meta:
        order_by = '-received_on'

