Note: This should be rewritten, I wrote it when I was first trying to understand
how fluff works.


How pillow/fluff work:
-----------------------

A Pillow provides the ability to listen to a database, and on changes, the class
`BasicPillow` calls change_transform and passes it the changed doc dict.  This
method can process the dict and transform it, or not.  The result is then
passed to the method ``change_transport``, which must be implemented in any
subclass of ``BasicPillow``.  This method is responsible for acting upon the
changes.

In fluff's case, it stores an indicator document with some data calculated from
a particular type of doc.  When a relevant doc is updated, the calculations are
performed.  The diff between the old and new indicator docs is calculated, and
sent to the db to update the indicator doc.

fluff's `Calculator` object auto-detects all methods that are decorated by 
subclasses of `base_emitter` and stores them in a `_fluff_emitters` array.
This is used by the `calculate` method to return a dict of emitter slugs mapped
to the result of the emitter function (called with the newly updated doc)
coerced to a list.

to rephrase:  fluff emitters accept a doc and return a generator where each
element corresponds to a contribution to the indicator
