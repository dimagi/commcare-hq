from django.conf.urls.defaults import *

urlpatterns = patterns('',                       
    url(r'^programs/list/?$', 'program.views.list_programs', name="list_programs"),
    url(r'^programs/add/?$', 'program.views.add_program', name="add_program"),
    url(r'^programs/edit/(?P<program_id>\d+)/?$', 'program.views.edit_program', name="edit_program"),
    url(r'^programs/delete/(?P<program_id>\d+)/?$', 'program.views.delete_program', name="delete_program"),
)