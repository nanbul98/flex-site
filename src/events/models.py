import mimetypes
import urllib
from datetime import date, timedelta

import embed_video
import os

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from django.db import models
from django.core.urlresolvers import reverse
from django.db.models.signals import post_save
from django.utils import timezone

from embed_video.backends import detect_backend, UnknownBackendException

# Create your models here.
from imagekit.models import ProcessedImageField
from pilkit.processors import ResizeToFill, SmartResize, ResizeToFit


class Category(models.Model):
    name = models.CharField(max_length=120)
    visible_in_event_list = models.BooleanField(default=False)
    description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Location(models.Model):
    room_number = models.CharField(max_length=20, unique=True, help_text="e.g. B201")
    name = models.CharField(max_length=120, null=True, blank=True, help_text="e.g. Hackerspace (or) Couture's Room")

    def __str__(self):
        return self.room_number
        # str = self.room_number
        # if self.name:
        #     str += " (" + self.name + ")"
        # return str

    def get_name(self):
        if self.name:
            return self.name
        else:
            return ""

    class Meta:
        ordering = ['room_number']


class BlockManager(models.Manager):
    def get_flex_1(self):
        return self.get_queryset().get(id=1)

    def get_flex_2(self):
        return self.get_queryset().get(id=2)


class Block(models.Model):
    name = models.CharField(max_length=20)
    start_time = models.TimeField()
    end_time = models.TimeField()

    objects = BlockManager()

    def __str__(self):
        return self.name

    def constant_string(self):
        if self.id == 1:
            return "FLEX1"
        else:
            return "FLEX2"

    def synervoice_string(self):
        return "F"


def default_event_date():
    today = date.today()
    # Wednesday = 2
    wednesday = today + timedelta((2 - today.weekday()) % 7)
    return wednesday


class EventManager(models.Manager):
    def all_for_date(self, event_date, block=None):
        if block:
            qs = block.event_set.all()
        else:
            qs = self.get_queryset()
        return qs.filter(date=event_date)

    def all_for_facilitator(self, user):
        return user.event_set.all()


class Event(models.Model):

    F1_XOR_F2 = 0
    F1_OR_F2 = 1
    F1_AND_F2 = 2
    MULTI_BLOCK_CHOICES = (
        (F1_XOR_F2, 'Can choose one or the other, but not both.'),
        (F1_OR_F2, 'Can choose one block or both blocks.'),
        (F1_AND_F2, 'Both blocks are required.'),
    )

    title = models.CharField(max_length=120)
    description = models.TextField(null=True, blank=True)  # MCE widget validation fails if required
    description_link = models.URLField(
        null=True, blank=True,
        help_text="An optional link to provide with the text description. If the link is to a video (YouTube or Vimeo) "
                  "or an image (png, jpg, or gif) it will be embedded with the description if there is enough "
                  "screen space.  If it is to another web page or a file, it will just display the link.")

    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    date = models.DateField(default=default_event_date)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    blocks = models.ManyToManyField(Block)
    multi_block_event = models.IntegerField(
        default=F1_OR_F2,
        choices=MULTI_BLOCK_CHOICES,
        help_text="If the event is running in more than one block, what restrictions are there for students?  "
                  "This field is ignored if the event only occurs during one block.")
    facilitators = models.ManyToManyField(User, related_name='events',
                                          limit_choices_to={'is_staff': True})
    allow_facilitators_to_modify = models.BooleanField(
        default=True,
        help_text="If false, only the creator of the event can edit.  If true, then any staff member that is listed as "
                  "a facilitator will be able to edit the event.  The creator will always be able to edit this event, "
                  "even if they are not listed as one of the facilitators.")
    registration_cut_off = models.IntegerField(
        "registration cut off [hours]",
        default=0,
        help_text="How many hours before the start of the flex block does registration close?  After this time, "
                  "students will no longer be able to register for the event, nor will they be able to delete it"
                  "if they've already registered.")
    max_capacity = models.PositiveIntegerField(
        default=30,
        help_text="The maximum number of students that can register for this event.  Once the maximum is reached, "
                  "students will no longer be able to register for this event.")

    # generally non-editable fields
    description_image_file = ProcessedImageField(upload_to='images/', null=True, blank=True,
                                                        processors=[ResizeToFit(400, 400, upscale=False)],
                                                        format='JPEG',
                                                        options={'quality': 80})
    creator = models.ForeignKey(User)
    updated_timestamp = models.DateTimeField(auto_now=True, auto_now_add=False)
    created_timestamp = models.DateTimeField(auto_now=False, auto_now_add=True)
    is_keypad_initialized = models.BooleanField(
        default=False,
        help_text="If keypad entry is required, leave this field false and turn it on through the event's attendance "
                  "page so that the proper scripts will run.")
    objects = EventManager()

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("events:detail", kwargs={"id": self.id})

    def cache_remote_image(self):
        """
        Take an image from the description field, download it to a temp file, and save it to the database in
        description_image_file.
        """
        if self.image():  # and not self.image_file:
            img_url = self.description_link
            img_temp = NamedTemporaryFile(delete=True)
            # http://stackoverflow.com/questions/24226781/changing-user-agent-in-python-3-for-urrlib-request-urlopen
            try:
                request = urllib.request.Request(
                    img_url,
                    data=None,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
                    }
                )
                img_temp.write(urllib.request.urlopen(request).read())
            except urllib.error.HTTPError:
                return False
            img_temp.flush()
            self.description_image_file.save(os.path.basename(img_url), File(img_temp))
            self.save()
            return True
        else:
            self.description_image_file = None
            self.save()
            return True

    def copy(self, num, copy_date=None, user=None, dates=[]):
        """
        Create a copy of this event, one week later, recursively num times.
        """
        if num > 0:
            if copy_date:
                new_date = copy_date
            else:
                new_date = self.date + timedelta(7)
                print(new_date)

            facilitators = self.facilitators.all()
            blocks = self.blocks.all()
            duplicate_event = self
            # https://docs.djangoproject.com/en/1.10/topics/db/queries/#copying-model-instances
            duplicate_event.pk = None  # autogen a new primary key (will create a new record)
            duplicate_event.date = new_date
            dates.append(new_date)
            if user is not None:
                duplicate_event.creator = user
            duplicate_event.save()
            duplicate_event.blocks.set(blocks)
            duplicate_event.facilitators.set(facilitators)
            dates = duplicate_event.copy(num - 1, dates=dates)  # recursive
        return dates


    def get_video_embed_link(self, backend):
        if type(backend) is embed_video.backends.YoutubeBackend:
            return "https://www.youtube.com/embed/" + backend.get_code() + "?rel=0"
        elif type(backend) is embed_video.backends.VimeoBackend:
            return "https://player.vimeo.com/video/" + backend.get_code()
        else:
            return None

    def get_image_url(self): #assumes its an image already.
        if self.description_image_file:
            return self.description_image_file.url
        else:
            return self.description_link

    def video(self):
        if not self.description_link:
            return None
        try:
            backend = detect_backend(self.description_link)

            return self.get_video_embed_link(backend)
        except UnknownBackendException:
            return None

    def image(self):
        if not self.description_link:
            return None
        # http://stackoverflow.com/questions/10543940/check-if-a-url-to-an-image-is-up-and-exists-in-python
        mimetype, encoding = mimetypes.guess_type(self.description_link)
        if mimetype and mimetype.startswith('image'):
            return self.description_link
        else:
            return None

    def both_required(self):
        blocks = self.blocks.all()
        if blocks.count() > 1 and self.multi_block_event == self.F1_AND_F2:
            return True
        else:
            return False

    def blocks_str(self):
        blocks = self.blocks.all()
        bl_str = ""
        count = 1
        for block in blocks:
            if count > 1:
                if self.multi_block_event == Event.F1_AND_F2:
                    bl_str += " AND "
                elif self.multi_block_event == Event.F1_OR_F2:
                    bl_str += " OR "
                elif self.multi_block_event == Event.F1_XOR_F2:
                    bl_str += " XOR "
                else:  # shouldn't get here
                    bl_str += " ERROR "
            bl_str += str(block)
            count += 1
        return bl_str

    def blocks_str_explanation(self):
        if self.blocks.all().count() > 1:
            return dict(Event.MULTI_BLOCK_CHOICES).get(self.multi_block_event)
        else:
            return None

    def block_selection_guide(self):
        blocks = self.blocks.all()
        if len(blocks) > 1:
            return self.multi_block_event
        elif blocks:  # only 1
            return blocks[0].constant_string()

    def flex1(self):
        if Block.objects.get_flex_1() in self.blocks.all():
            return True
        else:
            return False

    def flex2(self):
        if Block.objects.get_flex_2() in self.blocks.all():
            return True
        else:
            return False

    def facilitator_string(self):
        facilitators = self.facilitators.all()
        fac_str = ""
        count = 1
        for fac in facilitators:
            if count > 1:
                fac_str += ", "
            fac_str += fac.first_name + " " + fac.last_name
            count += 1
        return fac_str

    def get_editors(self):
        editors = [self.creator]
        if self.allow_facilitators_to_modify:
            for fac in self.facilitators.all():
                if fac not in editors:
                    editors += [fac]
        return editors

    def is_available(self, user, block):
        """
        Check if this event is available based on user's current registrations, attendance, and cutoff times
        :param user:
        :param block:
        :return: A tuple (boolean, string) where string is a reason for False
        """
        result = True, False, None
        if self.is_full(block):
            result = False, False, "This event is full."
        elif self.is_registration_closed(block):
            result = False, False, "The deadline to register for this event has passed."
        else:
            regs = user.registration_set.filter(event__date=self.date)
            for reg in regs:
                if reg.is_same(self, block):
                    result = False, True, "You are already registered for this event."
                    break
                else:
                    conflict_response = reg.is_conflict(self, block)
                if conflict_response is not None:
                    result = False, False, conflict_response
        return result

    def is_registration_closed(self, block):
        now = timezone.now()
        today_local = timezone.localtime(now)
        time = today_local.time()
        if self.date < today_local.date():
            result = True
        elif self.date > today_local.date():
            result = False
        else:  # same day
            result = block.start_time < today_local.time()
            # datetime = date
            # cut_off = (today_local + timedelta(hours=self.registration_cut_off)).time()
            # result = block.start_time < cut_off
        return result

    def is_full(self, block=None):
        """
        :param block:
        :return: If block=None return a boolean array with an element for each block this event occurs in.
        Otherwise, return only for the specified block
        """
        if block:
            is_full = self.get_attendances(block) >= self.max_capacity
        else:
            is_full = []
            for att in self.get_attendances(block):
                is_full.append(att >= self.max_capacity)
        return is_full

    def get_attendances(self, block=None):
        if block:
            result = self.registration_set.filter(block=block).count()
        else:
            result = []
            for block in self.blocks.all():
                result.append(self.registration_set.filter(block=block).count())
        return result


def event_post_save(sender, instance, **kwargs):
    post_save.disconnect(event_post_save, sender=sender)  # prevent recursion
    instance.cache_remote_image()
    post_save.connect(event_post_save, sender=sender)
post_save.connect(event_post_save, sender=Event)


class RegistrationManager(models.Manager):
    def create_registration(self, event, student, block):
        # need to check if student already has an event on that date in this block, if so, modify.
        reg = self.create(event=event,
                          student=student,
                          block=block,
                          absent=event.is_keypad_initialized
        )
        return reg

    def get_for_user_block_date(self, student, block, event_date):
        qs = self.get_queryset()
        return qs.filter(student=student).filter(event__date=event_date).filter(block=block)

    def registration_check(self, event_date, homeroom_teacher=None):
        if homeroom_teacher:
            students = User.objects.all().filter(
                is_staff=False,
                profile__homeroom_teacher=homeroom_teacher
            )
            # get queryset with events? optimization for less hits on db
            qs = self.get_queryset().filter(
                event__date=event_date,
                student__profile__homeroom_teacher=homeroom_teacher
            )
        else:
            students = User.objects.all().filter(is_staff=False)
            # get queryset with events? optimization for less hits on db
            qs = self.get_queryset().filter(event__date=event_date)

        students = students.values('id', 'username', 'first_name', 'last_name', 'profile__grade')

        for student in students:
            user_regs_qs = qs.filter(student_id=student['id'])

            for block in Block.objects.all():
                try:
                    reg = user_regs_qs.get(block=block)
                    student[block.constant_string()] = str(reg.event)
                except ObjectDoesNotExist:
                    student[block.constant_string()] = None

        return students

    def all_attendance(self, event_date):
        students = User.objects.all().filter(
            is_active=True,
            is_staff=False,
        )

        students = students.values('id',
                                   'username',
                                   'first_name',
                                   'last_name',
                                   'profile__grade',
                                   'profile__phone',
                                   'profile__email')
        students = list(students)

        # get queryset with events? optimization for less hits on db
        qs = self.get_queryset().filter(
            event__date=event_date,
        )
        for student in students:
            user_regs_qs = qs.filter(student_id=student['id'])

            for block in Block.objects.all():
                try:
                    reg = user_regs_qs.get(block=block)
                    if reg.absent and not reg.excused:
                        student[block.constant_string()] = block.synervoice_string()
                except ObjectDoesNotExist:
                    student[block.constant_string()] = block.synervoice_string()

        return students

    def attendance(self, flex_date):
        return self.get_queryset().filter(event__date=flex_date,
                                          student__is_active=True,
                                          student__is_staff=False,
                                          absent=True,
                                          excused=False,
                                          )


class Registration(models.Model):

    event = models.ForeignKey(Event)
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    block = models.ForeignKey(Block, on_delete=models.CASCADE)
    updated_timestamp = models.DateTimeField(auto_now=True, auto_now_add=False)
    created_timestamp = models.DateTimeField(auto_now=False, auto_now_add=True)
    absent = models.BooleanField(default=False)
    late = models.BooleanField(default=False)
    excused = models.BooleanField(default=False)

    objects = RegistrationManager()

    class Meta:
        # order_with_respect_to = 'event'
        unique_together = ("event", "student", "block")

    def __str__(self):
        return str(self.student) + ": " + str(self.event)

    def is_same(self, event, block):
        if self.event == event and self.block == block:
            return True
        else:
            return False

    def is_conflict(self, event, block, user=None, event_date=None):
        """
        :param event:
        :param block:
        :param user: if None assume the same user
        :param event_date: if None assume the same date
        :return: True if the event & block conflicts with this registration
        """
        result = None
        if (user and self.student is not user) or (event_date and event_date != self.event.date):
            result = None  # not same student or not same date
        else:
            if self.is_same(event, block):
                result = "You are already registered for this event."
            elif self.event == event and self.event.multi_block_event == Event.F1_XOR_F2:
                result = "You are already registered for this event in another block.  " \
                         "This event only allows registration in one block."
            elif self.event.both_required() or event.both_required():
                result = "This event conflicts with another event you are already registered for. " \
                    "You will need to remove the conflicting event before you can register for this one."
                # this event occurs in the same block (or multi block AND)
            elif self.block == block:
                if self.event.multi_block_event == Event.F1_OR_F2 or self.event.multi_block_event == Event.F1_XOR_F2:
                    result = "You are already registered for a different event in %s.  " \
                             "If you want to register for this event in another block, select the other block's tab " \
                             "at the top of this list." % str(block)
                else:
                    result = "You are already registered for a different event in %s." % str(block)

        # did I miss anything?
        return result

    def past_cut_off(self):
        return self.event.is_registration_closed(self.block)
