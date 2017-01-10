import csv
from datetime import date, datetime

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core import serializers
from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers import json
from django.forms import modelformset_factory, model_to_dict
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404, redirect

# Create your views here.
from django.urls import reverse_lazy, reverse
from django.utils.decorators import method_decorator
from django.views.generic import DeleteView
from profiles.models import Profile
from .models import Event, default_event_date, Registration, Block
from .forms import EventForm, AttendanceForm, AttendanceFormSetHelper, RegistrationForm, LocationForm


@staff_member_required
def location_create(request):
    form = LocationForm(request.POST or None)

    if form.is_valid():
        loc = form.save()
        messages.success(request, "New location added: <b>%s (%s)</b>" % (loc, loc.name))
        return redirect('events:create')

    context = {
        "title": "Add new location",
        "form": form,
        "btn_value": "Save"
    }
    return render(request, "events/location_form.html", context)


@staff_member_required
def event_create(request):
    form = EventForm(request.POST or None)

    if form.is_valid():
        event = form.save(commit=False)
        event.creator = request.user
        event.save()
        form.save_m2m()

        msg = "New event created for %s: <b>%s</b>" % (event.date, event.title)

        num_duplicates = form.cleaned_data['duplicate']
        if num_duplicates:
            dupe_dates = event.copy(num_duplicates, user=request.user)
            # http://stackoverflow.com/questions/9052433/overriding-default-format-when-printing-a-list-of-datetime-objects
            msg += "; duplicates made for %s." % ', '.join(map(str, dupe_dates))

        messages.success(request, msg)

        if not event.cache_remote_image():
            messages.warning(request, "Failed to properly cache your image.  Don't worry about it for now... unless "
                                      "you didn't provide an image link, in which case please let Tylere know!")

        block_id = event.blocks.all()[0].id
        date_query = event.date
        return redirect("%s?date=%s" % (reverse('events:list_by_block', args=(block_id,)), date_query))

    context = {
        "title": "Create Event",
        "form": form,
        "btn_value": "Save"
    }
    return render(request, "events/event_form.html", context)


@staff_member_required
def event_update(request, id=None):
    event = get_object_or_404(Event, id=id)

    form = EventForm(request.POST or None, instance=event)

    # not valid?
    if form.is_valid():
        event = form.save(commit=False)
        event.save()
        form.save_m2m()

        msg = "Edits saved for %s: <b>%s</b>" % (event.date, event.title)
        num_duplicates = form.cleaned_data['duplicate']
        if num_duplicates:
            dupe_dates = event.copy(num_duplicates, user=request.user)
            # http://stackoverflow.com/questions/9052433/overriding-default-format-when-printing-a-list-of-datetime-objects
            msg += "; duplicates made for %s." % ', '.join(map(str, dupe_dates))

        messages.success(request, msg)

        if not event.cache_remote_image():
            messages.warning(request, "Failed to properly cache your image.  Don't worry about it for now... unless "
                                      "you didn't provide an image link, in which case please let Tylere know!")


        block_id = event.blocks.all()[0].id
        date_query = event.date
        return redirect("%s?date=%s" % (reverse('events:list_by_block', args=(block_id,)), date_query))

    context = {
        "title": event.title,
        "delete_btn": True,
        "event": event,
        "form": form,
        "btn_value": "Save"
    }
    return render(request, "events/event_form.html", context)


@staff_member_required
def event_copy(request, id):
    new_event = get_object_or_404(Event, id=id)

    blocks = new_event.blocks.all()
    facilitators = new_event.facilitators.all()

    new_event.pk = None  # autogen a new primary key (quest_id by default)
    new_event.date = None

    d = {'blocks': blocks,
         'facilitators': facilitators,
         }

    form = EventForm(request.POST or None, instance=new_event, initial=d)

    # not valid?
    if form.is_valid():
        event = form.save()

        messages.success(request, "New event created for %s: <b>%s</b>" % (event.date, event.title))

        block_id = event.blocks.all()[0].id
        date_query = event.date
        return redirect("%s?date=%s" % (reverse('events:list_by_block', args=(block_id,)), date_query))

    context = {
        "title": new_event.title,
        "event": new_event,
        "form": form,
        "btn_value": "Save"
    }
    return render(request, "events/event_form.html", context)


def event_detail(request, id=None):
    instance = get_object_or_404(Event, id=id)
    context = {
        "title": instance.title,
        "event": instance,
    }
    return render(request, "events/event_detail.html", context)


@staff_member_required
def event_delete(request, id=None):
    event = get_object_or_404(Event, id=id)
    event.delete()
    messages.success(request, "Successfully deleted")
    return redirect("events/events:list")


@method_decorator(staff_member_required, name='dispatch')
class EventDelete(DeleteView):
    model = Event
    success_url = reverse_lazy('events:manage')


@staff_member_required
def event_manage(request):
    # date_query = request.GET.get("date", str(default_event_date()))
    # d = datetime.strptime(date_query, "%Y-%m-%d").date()

    queryset = Event.objects.filter(facilitators=request.user)

    # for event in queryset:
    #     for block in event.blocks.all():
    #         event.attendance = {}
    #         event.attendance = event.registration_set.filter().count()

    context = {
        # "date_filter": date_query,
        # "date_object": d,
        "title": "Your Events",
        "object_list": queryset,
        # "date_filter": d,
    }
    return render(request, "events/event_management.html", context)


@staff_member_required
def event_attendance_keypad(request, id=None, block_id=None):
    event = get_object_or_404(Event, id=id)
    # The first time this view is called, initialize the event for keypad entry
    # and set all the attendance to False
    if not event.is_keypad_initialized:
        registrations = event.registration_set.all()
        registrations.update(absent=True)
        event.is_keypad_initialized = True
        event.save()
    return event_attendance(request, id, block_id)


@staff_member_required
def event_attendance(request, id=None, block_id=None):
    event = get_object_or_404(Event, id=id)
    if block_id:
        active_block = get_object_or_404(Block, id=block_id)
    else:
        active_block = event.blocks.all()[0]

    queryset1 = Registration.objects.filter(event=event, block=active_block).order_by('student__last_name')

    # https://docs.djangoproject.com/en/1.9/topics/forms/modelforms/#model-formsets
    AttendanceFormSet1 = modelformset_factory(Registration,
                                              form=AttendanceForm,
                                              extra=0)
    helper = AttendanceFormSetHelper()

    if request.method =="POST":
        formset1 = AttendanceFormSet1(
            request.POST, request.FILES,
            queryset=queryset1,
            prefix='flex1'
        )
        if formset1.is_valid():
            formset1.save()
            messages.success(request, "Attendance saved for <b>%s</b> during <b>%s</b>" % (event, active_block))

    else:
        formset1 = AttendanceFormSet1(queryset=queryset1, prefix='flex1')

    context = {
        "object_list_1": queryset1,
        "event": event,
        "formset1": formset1,
        "helper": helper,
        "active_block": active_block,
    }
    return render(request, "events/attendance.html", context)


def event_list(request, block_id=None):
    date_query = request.GET.get("date", str(default_event_date()))
    d = datetime.strptime(date_query, "%Y-%m-%d").date()

    if block_id:
        active_block = get_object_or_404(Block, id=block_id)
    else:
        active_block = Block.objects.all()[0]

    blocks = Block.objects.all()
    blocks_json = serializers.serialize('json', blocks, fields=('id', 'name', ))

    queryset = active_block.event_set.filter(date=d, category__visible_in_event_list=True)

    registrations = {}
    if request.user.is_authenticated():
        # Build a dictionary of user's registrations for this day:
        # {block_name: event,}
        registrations = {}
        for block in blocks:
            try:
                reg = Registration.objects.get(student=request.user, block=block, event__date=d)
            except Registration.DoesNotExist:
                reg = None
            registrations[block] = reg

    for event in queryset:
        event.attendance = event.registration_set.filter(block=active_block).count()
        if request.user.is_authenticated():
            event.available, event.already, event.explanation = event.is_available(request.user, active_block)
        else:
            event.available = True

    context = {
        "date_filter": date_query,
        "date_object": d,
        "title": "List",
        "object_list": queryset,
        "registrations": registrations,
        "blocks_json": blocks_json,
        "blocks": blocks,
        "active_block": active_block,
    }
    return render(request, "events/event_list.html", context)


@login_required
def staff_locations(request):
    date_query = request.GET.get("date", str(default_event_date()))
    d = datetime.strptime(date_query, "%Y-%m-%d").date()

    users = User.objects.filter(is_staff=True).values('id', 'first_name', 'last_name')
    users = list(users)

    events = Event.objects.filter(date=d)

    for user in users:
        user_events = events.filter(facilitators__id=user['id'])

        for block in Block.objects.all():
            try:
                block_events = user_events.filter(blocks=block)
                user[block.constant_string()] = block_events
            except ObjectDoesNotExist:
                user[block.constant_string()] = None

    context = {
        "date_filter": date_query,
        "date_object": d,
        "users": users,
    }
    return render(request, "events/staff.html", context)


@staff_member_required
def generate_synervoice_csv(request, d):
    # def blocks_absent(s):
    #     str = ""
    #     if 'FLEX1' in s:
    #         str += s['FLEX1']
    #     if 'FLEX2' in s:
    #         str += s['FLEX2']
    #     return str

    d_str = d.strftime("%y%m%d")
    attendance_data = Registration.objects.all_attendance(d)
    # A 8th column exists if the student was absent or didn't register
    absent_data = [s for s in attendance_data if len(s) > 7]

    # https://docs.djangoproject.com/en/1.10/howto/outputting-csv/
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="synervoice.csv"'

    writer = csv.writer(response)
    for s in absent_data:
        writer.writerow([s['last_name'] + ", " + s['first_name'],
                         s['username'],
                         s['profile__grade'],
                         s['profile__phone'],
                         d_str,
                         "F",  # blocks_absent(s),  # Add F regardless of whether absent or didn't register, one or both
                        ])

    return response


@staff_member_required
def synervoice(request):
    date_query = request.GET.get("date", str(default_event_date()))
    d = datetime.strptime(date_query, "%Y-%m-%d").date()

    if request.method == "POST":
        event_date = request.POST.get("date")
        d = datetime.strptime(event_date, "%Y-%m-%d").date()
        return generate_synervoice_csv(request, d)

    context = {
        "date_filter": date_query,
        "d": d,
    }

    return render(request, "events/synervoice.html", context)


###############################################
#
#       REGISTRATION VIEWS
#
################################################
@login_required
def registrations_list(request):
    queryset = Registration.objects.filter(student=request.user)
    context = {
        "object_list": queryset
    }
    return render(request, "events/registration_list.html", context)


@login_required
def register(request, id, block_id):
    date_query = request.GET.get("date", str(default_event_date()))
    event = get_object_or_404(Event, id=id)
    block = get_object_or_404(Block, id=block_id)

    available, already, reason = event.is_available(request.user, block)

    block_text = ""
    if available:
        if event.both_required():
            for block in event.blocks.all():
                Registration.objects.create_registration(event=event, student=request.user, block=block)
                block_text += str(block) + " "

        else:
            Registration.objects.create_registration(event=event, student=request.user, block=block)
            block_text = str(block)

        messages.success(request, "Successfully registered for <b>%s</b> during <b>%s</b> " % (event, block_text))
    else:
        messages.warning(request, "<i class='fa fa-exclamation-triangle'></i> %s" % reason)
    return redirect("%s?date=%s" % (reverse('events:list_by_block', args=(block_id,)), date_query))


@login_required
def registrations_delete(request, id=None):
    reg = get_object_or_404(Registration, id=id)
    if reg.event.both_required():
        # maybe try/except instead?
        # Delete all records of this event (i.e. for all blocks)
        regs = Registration.objects.filter(event=reg.event, student=reg.student)
        regs.delete()
    else:
        reg.delete()
    messages.success(request, "You've been removed from <b>%s</b>" % reg.event)

    # Return to page that got us here.
    # http://stackoverflow.com/questions/12758786/redirect-return-to-same-previous-page-in-django
    # Don't do this with forms/POST
    if request.META:  # this can be turned off, so need to check
        return redirect(request.META.get('HTTP_REFERER'))
    else:
        return redirect('events:registrations_list')


@login_required
def registrations_manage(request):
    queryset = Registration.objects.filter(student=request.user)
    context = {
        "object_list": queryset
    }
    return render(request, "events/registration_list.html", context)


@staff_member_required
def registrations_homeroom(request, user_id=None):
    date_query = request.GET.get("date", str(default_event_date()))
    d = datetime.strptime(date_query, "%Y-%m-%d").date()

    if user_id:
        homeroom_teacher = get_object_or_404(User, id=user_id)
    else:
        homeroom_teacher = request.user

    # profile_queryset = Profile.objects.select_related('user').filter(homeroom_teacher=homeroom_teacher)
    # # profile_queryset.annotate()  # runs the query? why?

    students = Registration.objects.registration_check(d, homeroom_teacher)

    context = {
        "heading": "Homeroom Students for " + homeroom_teacher.get_full_name(),
        "students": students,
        "date_filter": date_query,
        "date_object": d,
    }
    return render(request, "events/homeroom_list.html", context)


@staff_member_required
def registrations_all(request):
    date_query = request.GET.get("date", str(default_event_date()))
    d = datetime.strptime(date_query, "%Y-%m-%d").date()

    students = Registration.objects.registration_check(d)

    context = {
        "heading": "All Student Registrations",
        "students": students,
        "date_filter": date_query,
        "date_object": d,
    }
    return render(request, "events/homeroom_list.html", context)