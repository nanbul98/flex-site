from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def login(request, model=None):
    return HttpResponse(model)

def getblocks(request):
    return HttpResponse('blocks')
