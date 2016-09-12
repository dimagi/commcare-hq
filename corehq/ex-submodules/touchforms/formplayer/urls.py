from django.conf.urls import *
from touchforms.formplayer.models import XForm

xform_info = {
    "queryset" : XForm.objects.order_by('namespace'),
}

urlpatterns = patterns('',
    url(r'^$', 'touchforms.formplayer.views.xform_list', name="xform_list"),
    url(r'^enter/(?P<xform_id>.*)$', 'touchforms.formplayer.views.enter_form', name='xform_play'),
    url(r'^enterkb/(?P<xform_id>.*)$', 'touchforms.formplayer.views.enter_form', {'input_mode': 'type'}, name='xform_play_kb'),
    url(r'^enterall/(?P<xform_id>.*)$', 'touchforms.formplayer.views.enter_form', {'input_mode': 'full'}, name='xform_play_all'),
    url(r'^enteroffline/(?P<xform_id>.*)$', 'touchforms.formplayer.views.enter_form',
        {'input_mode': 'full', 'offline': True}, name='xform_play_offline'),
    url(r'^download/(?P<xform_id>.*)$', 'touchforms.formplayer.views.download', name='xform_download'),
    url(r'^player_proxy$', 'touchforms.formplayer.views.player_proxy', name='xform_player_proxy'),
    url(r'^api/preload/$', 'touchforms.formplayer.views.api_preload_provider', name='xform_preloader'),
    url(r'^api/autocomplete/$', 'touchforms.formplayer.views.api_autocomplete', name='touchforms_autocomplete'),
    url(r'^player-abort/$', 'touchforms.formplayer.views.player_abort', name='touchforms_force_abort'),
)
