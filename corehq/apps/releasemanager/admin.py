from django.contrib import admin
from corehq.apps.releasemanager.models import Jarjad, ResourceSet, Build

admin.site.register(Jarjad)
admin.site.register(ResourceSet)
admin.site.register(Build)