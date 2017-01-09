from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$blocks', views.getblocks, name='getblocks'),
    url(r'^(?P<model>\w+)/$', views.login, name='login'),
]
