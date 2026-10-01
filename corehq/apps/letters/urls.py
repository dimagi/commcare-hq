from django.urls import re_path as url

from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.apps.letters.views import (
    LetterTemplateCreateView,
    LetterTemplateDeleteView,
    LetterTemplateEditView,
    LetterTemplateListView,
    LetterTemplatePreviewView,
)

urlpatterns = [
    url(r'^$', LetterTemplateListView.as_view(), name=LetterTemplateListView.urlname),
    url(r'^new/$', waf_allow('XSS_BODY')(LetterTemplateCreateView.as_view()),
        name=LetterTemplateCreateView.urlname),
    url(r'^preview/$', waf_allow('XSS_BODY')(LetterTemplatePreviewView.as_view()),
        name=LetterTemplatePreviewView.urlname),
    url(r'^(?P<template_id>\d+)/$', waf_allow('XSS_BODY')(LetterTemplateEditView.as_view()),
        name=LetterTemplateEditView.urlname),
    url(r'^(?P<template_id>\d+)/delete/$', LetterTemplateDeleteView.as_view(),
        name=LetterTemplateDeleteView.urlname),
]
