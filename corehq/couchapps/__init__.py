from corehq.preindex import CouchAppsPreindexPlugin

CouchAppsPreindexPlugin.register('couchapps', __file__, {
    'form_question_schema': 'meta'
})
