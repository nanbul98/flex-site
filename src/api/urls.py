from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^blocks/$', views.getblocks, name='getblocks'),
    url(r'^create_auth_token/$', views.create_auth_token, name='getblocks')
]
