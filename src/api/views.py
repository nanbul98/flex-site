# Imports
from django.shortcuts import render
from django.http import HttpResponse
from django.db.models.signals import post_save
from events.models import Event, default_event_date, Registration, Block
from django.core import serializers
from django.contrib.auth.models import User
from django.dispatch import receiver

# DJango Rest Framework
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.views import APIView
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import authentication, permissions

from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from django.conf import settings

# This code is triggered whenever a new user has been created and saved to the database

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)


def getblocks(request):
    blocks = serializers.serialize("json", Event.objects.all())
    return HttpResponse(blocks)
