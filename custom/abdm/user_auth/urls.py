from django.urls import path

from custom.abdm.const import GATEWAY_CALLBACK_URL_PREFIX
from custom.abdm.user_auth.views import (
    AuthConfirm,
    AuthFetchModes,
    AuthInit,
    GatewayAuthOnConfirm,
    GatewayAuthOnFetchModes,
    GatewayAuthOnInit,
)

user_auth_urls = [
    path('api/user_auth/fetch_auth_modes', AuthFetchModes.as_view(), name='fetch_auth_modes'),
    path('api/user_auth/auth_init', AuthInit.as_view(), name='auth_init'),
    path('api/user_auth/auth_confirm', AuthConfirm.as_view(), name='auth_confirm'),

    # APIS that will be triggered by ABDM Gateway
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/users/auth/on-fetch-modes', GatewayAuthOnFetchModes.as_view(),
         name='gateway_auth_on_fetch_modes'),
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/users/auth/on-init', GatewayAuthOnInit.as_view(),
         name='gateway_auth_on_init'),
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/users/auth/on-confirm', GatewayAuthOnConfirm.as_view(),
         name='gateway_auth_on_confirm'),
]
