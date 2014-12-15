from django.conf.urls.defaults import patterns, url
from corehq.apps.programs.views import (
    ProgramListView, FetchProgramListView, NewProgramView, EditProgramView,
    FetchProductForProgramListView
)

settings_urls = patterns('corehq.apps.programs.views',
    url(r'^$', ProgramListView.as_view(), name=ProgramListView.urlname),
    url(r'^list/$', FetchProgramListView.as_view(), name=FetchProgramListView.urlname),
    url(r'^new/$', NewProgramView.as_view(), name=NewProgramView.urlname),
    url(r'^(?P<prog_id>[\w-]+)/$', EditProgramView.as_view(), name=EditProgramView.urlname),
    url(r'^(?P<prog_id>[\w-]+)/productlist/$', FetchProductForProgramListView.as_view(),
        name=FetchProductForProgramListView.urlname),
    url(r'^delete/(?P<prog_id>[\w-]+)/$', 'delete_program', name='delete_program'),
)
