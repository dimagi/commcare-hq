from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url
from corehq.apps.programs.views import (
    ProgramListView, FetchProgramListView, NewProgramView, EditProgramView,
    FetchProductForProgramListView,
    delete_program,
)

settings_urls = [
    url(r'^$', ProgramListView.as_view(), name=ProgramListView.urlname),
    url(r'^list/$', FetchProgramListView.as_view(), name=FetchProgramListView.urlname),
    url(r'^new/$', NewProgramView.as_view(), name=NewProgramView.urlname),
    url(r'^(?P<prog_id>[\w-]+)/$', EditProgramView.as_view(), name=EditProgramView.urlname),
    url(r'^(?P<prog_id>[\w-]+)/productlist/$', FetchProductForProgramListView.as_view(),
        name=FetchProductForProgramListView.urlname),
    url(r'^delete/(?P<prog_id>[\w-]+)/$', delete_program, name='delete_program'),
]
