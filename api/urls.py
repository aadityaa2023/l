"""API url shim that re-uses `mobileapi`'s urls.

This keeps existing `include('api.urls')` references working while
centralizing API routing inside `mobileapi`.
"""
from django.urls import include, path

urlpatterns = [
    path('', include('mobileapi.urls')),
]
