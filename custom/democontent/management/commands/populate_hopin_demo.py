"""
Populates a HOP IN CMS5 instance with a fuller, English-language set of demo
data, modelled directly on the association's real 2025/26 teaching plan and
event calendar (source: the "Plano Pedagogico" and "Eventos HOP IN" Google
Sheets, plus the "Sobre Workshops" doc, as of 2026-08-31). This supersedes
create_hopin_demo_data.py in scope (more instructors, more classes, real
socials/events, per-instructor logins, and sample registrations with both
completed and pending payments) but does not replace it — both remain in
the repo since create_hopin_demo_data.py also builds the homepage/CMS pages,
which this script intentionally leaves untouched.

Where the source spreadsheet was ambiguous, blank, or marked "TBD"
(e.g. exact times/dates for two of the September workshops, prices for the
non-JAM social nights), a reasonable placeholder is used and flagged in a
comment below — check against the live sheet before treating those as firm.

Dual-purpose file: this is both a normal Django management command
(``python3 manage.py populate_hopin_demo``, once the ``democontent`` app is
installed) and a standalone script (``python3 populate_hopin_demo.py``,
after copying it onto a host where django-danceschool is installed but
``democontent`` is not in INSTALLED_APPS — e.g. the "vanilla PR #187" CMS5
instance). The bootstrap block below only runs in the latter case.

Safe to run more than once: get_or_create everywhere for reference data;
instructor/staff/volunteer accounts are updated in place; regular classes,
workshops and events are skipped (not duplicated) if a Series/PublicEvent
for that title already exists at that location. Sample registrations ARE
created fresh on every run (there is no natural unique key for a walk-in
registration) -- rerun only if you want more of them.

Usage:
    python3 manage.py populate_hopin_demo
    # or, standalone (no democontent app installed):
    python3 populate_hopin_demo.py
"""
import os
import sys

import django
from django.apps import apps

if not apps.ready:
    # Standalone-script bootstrap. Only fires when this file is executed
    # directly (python3 populate_hopin_demo.py) rather than imported as a
    # management command, in which case manage.py already did this.
    sys.path.insert(0, '/data/web')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school.settings')
    django.setup()

from datetime import datetime, timedelta  # noqa: E402

from django.contrib.auth.models import Group, User  # noqa: E402
from django.core.management.base import BaseCommand  # noqa: E402
from django.utils import timezone  # noqa: E402
from django.utils.text import slugify  # noqa: E402

from danceschool.core.constants import getConstant  # noqa: E402
from danceschool.core.models import (  # noqa: E402
    ClassDescription, Customer, DanceRole, DanceType, DanceTypeLevel, Event,
    EventOccurrence, EventRegistration, EventStaffMember, Instructor,
    Invoice, InvoiceItem, Location, PricingTier, PublicEvent, Registration,
    Series, StaffMember,
)


def aware(y, m, d, hh, mm):
    return timezone.make_aware(datetime(y, m, d, hh, mm))


class Command(BaseCommand):
    help = (
        'Populates a HOP IN CMS5 instance with a fuller English-language '
        'demo dataset: the real 2025/26 class schedule, September 2026 '
        'workshops, the social/event calendar, per-instructor logins, and '
        'some sample registrations (paid and pending).'
    )

    def handle(self, *args, **options):
        self.now = timezone.now()
        self._make_roles_and_types()
        self._make_locations()
        self._make_instructors_and_logins()
        self._make_staff_and_volunteer_logins()
        self._make_pricing()
        self._make_regular_classes()
        self._make_september_workshops()
        self._make_events()
        self._make_sample_registrations()
        self.stdout.write(self.style.SUCCESS(
            'HOP IN demo data populated successfully.'
        ))

    # ------------------------------------------------------------------
    # Roles, dance types & levels
    # ------------------------------------------------------------------
    def _make_roles_and_types(self):
        # setupschool's own "define roles" prompt creates a redundant
        # 'Leader'/'Follower' pair (see CLAUDE.md) -- replace with the
        # canonical Lead/Follow/Solo/Switch set used throughout this script.
        DanceRole.objects.filter(name__in=['Leader', 'Follower']).delete()
        self.lead, _ = DanceRole.objects.get_or_create(name='Lead', defaults={'order': 1})
        self.follow, _ = DanceRole.objects.get_or_create(name='Follow', defaults={'order': 2})
        self.solo_role, _ = DanceRole.objects.get_or_create(
            name='Solo', defaults={'pluralName': 'Solo', 'order': 3}
        )
        self.switch_role, _ = DanceRole.objects.get_or_create(
            name='Switch', defaults={'pluralName': 'Switch', 'order': 4}
        )

        self.lindy, _ = DanceType.objects.get_or_create(name='Lindy Hop', defaults={'order': 1})
        self.lindy.roles.set([self.lead, self.follow, self.switch_role])
        self.jazz, _ = DanceType.objects.get_or_create(
            name='Solo Jazz / Authentic Jazz', defaults={'order': 2}
        )
        self.jazz.roles.set([self.solo_role])
        self.tap, _ = DanceType.objects.get_or_create(name='Tap', defaults={'order': 3})
        self.tap.roles.set([self.solo_role])
        self.shag, _ = DanceType.objects.get_or_create(name='Shag', defaults={'order': 4})
        self.shag.roles.set([self.lead, self.follow, self.switch_role])

        # setupschool's generic 'Level 1'/'Level 2'/'Level 3' (on whatever
        # DanceType it created interactively) are left alone if anything
        # already references them, and deleted otherwise -- this script
        # uses its own, named levels below.
        DanceTypeLevel.objects.filter(
            name__in=['Level 1', 'Level 2', 'Level 3'], classdescription__isnull=True
        ).delete()

        self.levels = {}
        level_specs = [
            (self.lindy, ['Beginner', 'Intermediate (1/2)', 'Advanced (3)', 'Training Class']),
            (self.jazz, ['Beginner', 'Intermediate (1/2)', 'Advanced (3)']),
            (self.tap, ['Beginner']),
            (self.shag, ['Beginner']),
        ]
        for dt, names in level_specs:
            for i, name in enumerate(names, start=1):
                lvl, _ = DanceTypeLevel.objects.get_or_create(
                    name=name, danceType=dt, defaults={'order': i}
                )
                self.levels[(dt.name, name)] = lvl
        self.stdout.write('Roles, dance types & levels ok.')

    # ------------------------------------------------------------------
    # Locations
    # ------------------------------------------------------------------
    def _make_locations(self):
        # No real address is on file yet for the regular weekly classes
        # (the Plano Pedagogico sheet only has schedule/content, not a
        # venue) -- kept as placeholder studio names, as in
        # create_demo_data.py. Cafe Ceuta, on the other hand, is the real,
        # named venue for the regular social nights (source: "Eventos HOP
        # IN" > Agenda/Locais sheets) -- exact street address not on file,
        # left blank rather than invented.
        self.studio, _ = Location.objects.get_or_create(
            name='HOP IN Studio - Bonfim',
            defaults=dict(
                status=Location.StatusChoices.active,
                address='Rua de Exemplo 123', city='Porto', state='Porto',
                zip='4300-001', directions='Near the Bonfim metro station.',
                defaultCapacity=40,
            )
        )
        self.hall, _ = Location.objects.get_or_create(
            name='HOP IN Hall - Centro',
            defaults=dict(
                status=Location.StatusChoices.active,
                address='Rua Central 45', city='Porto', state='Porto',
                zip='4000-001', directions='Central Porto.',
                defaultCapacity=80,
            )
        )
        self.cafe_ceuta, _ = Location.objects.get_or_create(
            name='Cafe Ceuta',
            defaults=dict(
                status=Location.StatusChoices.active,
                address='Cafe Ceuta', city='Porto', state='Porto',
                zip='', directions='Regular Wednesday-night social venue.',
                defaultCapacity=60,
            )
        )
        self.stdout.write('Locations ok.')

    # ------------------------------------------------------------------
    # Instructors + one login per instructor (group: Instructor)
    # ------------------------------------------------------------------
    def _make_instructors_and_logins(self):
        # Names and rough teaching areas as they appear across the
        # Horarios_2025_2026 and Workshops Setembro sheets. Last names are
        # not in the source (first names only) -- approximated here, same
        # caveat as create_hopin_demo_data.py.
        instructors_data = [
            ('Teresa', 'Nogueira', 'Lindy Hop and Solo Jazz instructor; welcomes new dancers in the beginner classes.'),
            ('Paulo', 'Ferreira', "Lindy Hop and Solo Jazz instructor; Teresa's regular teaching partner for the beginner classes."),
            ('Gabriela', 'Marques', 'Solo Jazz / Authentic Jazz and Tap instructor.'),
            ('Luisa', 'Pinto', 'Lindy Hop and Tap instructor; also helps run the Training Class.'),
            ('Ian', 'Cardoso', 'Lindy Hop instructor, teaching the more advanced classes.'),
            ('Mariana', 'Sousa', 'Lindy Hop instructor; helps run the Training Class.'),
            ('Uriel', 'Duarte', 'Shag instructor.'),
            ('Katia', 'Ramos', 'Shag instructor.'),
            ('Ines', 'Carvalho', 'Lindy Hop instructor; helps run the Training Class.'),
            ('Marta', 'Coelho', 'Guest instructor for the Followers Choice workshop, focused on musicality and styling for the follow role.'),
        ]
        self.instr = {}
        instructor_group = Group.objects.filter(name='Instructor').first()
        if not instructor_group:
            self.stdout.write(self.style.WARNING(
                "Group 'Instructor' does not exist (run setupschool first) - "
                "instructor logins created without a group."
            ))

        for first, last, bio in instructors_data:
            sm, _ = StaffMember.objects.get_or_create(
                firstName=first, lastName=last, defaults=dict(bio=bio)
            )
            if sm.bio != bio:
                sm.bio = bio
                sm.save()
            Instructor.objects.get_or_create(
                staffMember=sm, defaults={'status': Instructor.InstructorStatus.roster}
            )

            username = first.lower()
            email = '%s@hopin.pt' % username
            user, _ = User.objects.get_or_create(
                username=username, defaults={'email': email, 'first_name': first, 'last_name': last}
            )
            user.email = email
            user.first_name = first
            user.last_name = last
            user.is_staff = True
            user.set_password('hopintest')
            user.save()
            if instructor_group:
                user.groups.add(instructor_group)
            if sm.userAccount_id != user.id:
                sm.userAccount = user
                sm.save()

            self.instr[first] = sm
        self.stdout.write('Instructors + logins ok (%d accounts, password hopintest).' % len(instructors_data))

    # ------------------------------------------------------------------
    # 1 Board (staff) login + 2 Registration Desk (volunteer) logins
    # ------------------------------------------------------------------
    def _make_staff_and_volunteer_logins(self):
        # Names taken from the "Equipa" sheet in "Eventos HOP IN",
        # excluding anyone already given an instructor login above, so
        # each demo account maps to exactly one group.
        accounts = [
            ('elene', 'Elene', 'Barbosa', 'Board', 'elene@hopin.pt'),
            ('francisca', 'Francisca', 'Amaral', 'Registration Desk', 'francisca@hopin.pt'),
            ('catarina', 'Catarina', 'Vidal', 'Registration Desk', 'catarina@hopin.pt'),
        ]
        for username, first, last, group_name, email in accounts:
            user, _ = User.objects.get_or_create(
                username=username, defaults={'email': email, 'first_name': first, 'last_name': last}
            )
            user.email = email
            user.first_name = first
            user.last_name = last
            user.is_staff = True
            user.set_password('hopintest')
            user.save()
            group = Group.objects.filter(name=group_name).first()
            if group:
                user.groups.add(group)
            else:
                self.stdout.write(self.style.WARNING(
                    "Group '%s' does not exist (run setupschool first) - "
                    "account '%s' created without a group." % (group_name, username)
                ))
        self.stdout.write('Board + Registration Desk logins ok (password hopintest).')

    # ------------------------------------------------------------------
    # Pricing (from the "Precos" sheet)
    # ------------------------------------------------------------------
    def _make_pricing(self):
        self.pares, _ = PricingTier.objects.get_or_create(
            name='Partnered - Monthly Module',
            defaults={'onlinePrice': 30, 'doorPrice': 35, 'dropinPrice': 10}
        )
        self.solo, _ = PricingTier.objects.get_or_create(
            name='Solo - Monthly Module',
            defaults={'onlinePrice': 25, 'doorPrice': 30, 'dropinPrice': 8}
        )
        # Both derived from the sheet's per-session discount table (1
        # session = 15 EUR, 2 sessions = 25 EUR total).
        self.workshop_2session, _ = PricingTier.objects.get_or_create(
            name='HOP INto Workshop (2 sessions)',
            defaults={'onlinePrice': 25, 'doorPrice': 30, 'dropinPrice': 15}
        )
        self.workshop_1session, _ = PricingTier.objects.get_or_create(
            name='HOP INto Workshop (1 session)',
            defaults={'onlinePrice': 15, 'doorPrice': 18, 'dropinPrice': 15}
        )
        # Prices for the regular Wednesday social nights and the bigger
        # end-of-term parties are not yet decided in the source sheet
        # (blank "Preco" column) -- modelled as free/door-only for now.
        self.social_free, _ = PricingTier.objects.get_or_create(
            name='Social Night (free entry, TBD)',
            defaults={'onlinePrice': 0, 'doorPrice': 0, 'dropinPrice': 0}
        )
        self.jam_price, _ = PricingTier.objects.get_or_create(
            name='HOP IN JAM',
            defaults={'onlinePrice': 10, 'doorPrice': 10, 'dropinPrice': 10}
        )
        self.stdout.write('Pricing ok.')

    # ------------------------------------------------------------------
    # Regular 2025/26 season classes (Horarios_2025_2026, "TO-BE" plan)
    # ------------------------------------------------------------------
    def _make_regular_classes(self):
        instructor_category = getConstant('general__eventStaffCategoryInstructor')

        def make_series(title, level, location, pricing, teachers, weeks, start, description=''):
            cd, _ = ClassDescription.objects.get_or_create(
                title=title, danceTypeLevel=level,
                defaults={'description': description, 'slug': slugify(title)}
            )
            if Series.objects.filter(classDescription=cd, location=location).exists():
                return
            s = Series(
                classDescription=cd, pricingTier=pricing, location=location,
                status=Event.RegStatus.enabled,
            )
            s.save()
            for w in range(weeks):
                EventOccurrence.objects.create(
                    event=s,
                    startTime=start + timedelta(weeks=w),
                    endTime=start + timedelta(weeks=w, hours=1, minutes=15),
                )
            for t in teachers:
                ssm = EventStaffMember.objects.create(
                    event=s, category=instructor_category, staffMember=self.instr[t],
                )
                ssm.occurrences.set(s.eventoccurrence_set.all())
                ssm.save()
            s.save()

        # Season start: first Tuesday/Wednesday/Thursday of October 2026,
        # matching the "Out-Dez" first trimester in PlanoAulas_25_26.
        tue = aware(2026, 10, 6, 18, 30)
        wed = aware(2026, 10, 7, 18, 30)
        thu = aware(2026, 10, 8, 18, 30)

        make_series(
            'Beginner Authentic Jazz', self.levels[('Solo Jazz / Authentic Jazz', 'Beginner')],
            self.studio, self.solo, ['Teresa', 'Paulo'], weeks=12, start=tue,
            description=(
                'Term-long beginner class in Authentic Jazz: simple sequences '
                'built by the instructors, foundational steps, and historical '
                'choreographies such as Shim Sham and the Jitterbug Stroll.'
            ),
        )
        make_series(
            'Beginner Lindy Hop', self.levels[('Lindy Hop', 'Beginner')],
            self.studio, self.pares, ['Teresa', 'Paulo'], weeks=12, start=tue.replace(hour=19, minute=45),
            description=(
                'Term-long beginner class in Lindy Hop: groove walk and triple '
                'step, in 6- and 8-count patterns.'
            ),
        )
        make_series(
            'Authentic Jazz - Advanced Module', self.levels[('Solo Jazz / Authentic Jazz', 'Advanced (3)')],
            self.hall, self.solo, ['Paulo', 'Luisa', 'Teresa', 'Gabriela'], weeks=4, start=wed,
            description=(
                'Monthly thematic module, with instructors rotating through '
                'the year. First module: Shim Sham variation (Al and Leon).'
            ),
        )
        make_series(
            'Lindy Hop - Advanced Module', self.levels[('Lindy Hop', 'Advanced (3)')],
            self.hall, self.pares, ['Ian', 'Luisa', 'Mariana'], weeks=4, start=wed.replace(hour=19, minute=45),
            description=(
                'Monthly thematic module: Swing Out Lab - refining the swing '
                'out and its variations.'
            ),
        )
        make_series(
            'Authentic Jazz - Intermediate Module', self.levels[('Solo Jazz / Authentic Jazz', 'Intermediate (1/2)')],
            self.studio, self.solo, ['Gabriela', 'Paulo'], weeks=4, start=thu,
            description='Monthly thematic module: Shim Sham variation 1 (Al and Leon).',
        )
        make_series(
            'Lindy Hop - Intermediate Module', self.levels[('Lindy Hop', 'Intermediate (1/2)')],
            self.studio, self.pares, ['Gabriela', 'Paulo'], weeks=4, start=thu.replace(hour=19, minute=45),
            description='Monthly thematic module: Swing Out Lab - refining the swing out and its variations.',
        )
        make_series(
            'Lindy Hop Training Class', self.levels[('Lindy Hop', 'Training Class')],
            self.studio, self.pares, ['Mariana', 'Ines', 'Luisa'], weeks=12, start=thu.replace(hour=21, minute=15),
            description='Coached training class for dancers who already have a solid grasp of Lindy Hop.',
        )
        self.stdout.write('Regular 2025/26 classes ok.')

    # ------------------------------------------------------------------
    # September 2026 workshops (Workshops Setembro sheet: real dates/
    # prices/teachers)
    # ------------------------------------------------------------------
    def _make_september_workshops(self):
        instructor_category = getConstant('general__eventStaffCategoryInstructor')

        def make_workshop(title, level, teachers, pricing, dates_times, description=''):
            cd, _ = ClassDescription.objects.get_or_create(
                title=title, danceTypeLevel=level,
                defaults={'description': description, 'slug': slugify(title)}
            )
            if Series.objects.filter(classDescription=cd, location=self.studio).exists():
                return
            s = Series(
                classDescription=cd, pricingTier=pricing, location=self.studio,
                status=Event.RegStatus.enabled, allowDropins=True,
            )
            s.save()
            for (y, m, d, sh, sm_, eh, em) in dates_times:
                EventOccurrence.objects.create(
                    event=s, startTime=aware(y, m, d, sh, sm_), endTime=aware(y, m, d, eh, em),
                )
            for t in teachers:
                ssm = EventStaffMember.objects.create(
                    event=s, category=instructor_category, staffMember=self.instr[t],
                )
                ssm.occurrences.set(s.eventoccurrence_set.all())
                ssm.save()
            s.save()

        make_workshop(
            'HOP INto Solo Basics', self.levels[('Solo Jazz / Authentic Jazz', 'Beginner')],
            ['Teresa'], self.workshop_2session,
            [(2026, 9, 15, 18, 30, 19, 30), (2026, 9, 22, 18, 30, 19, 30)],
            description=(
                'Swing music makes your foot tap along almost on its own -- but '
                'how do you dance it? Yes, you really can dance to jazz, play '
                'with its rhythms and syncopation, and become the visible form '
                'of the music. With iconic steps like the fall off the log, '
                'shoe-shine, scarecrow and drunk sailor, this is a dance for '
                'people who do not take themselves too seriously. Intrigued? '
                'Come find out for yourself!'
            ),
        )
        make_workshop(
            'HOP INto Lindy Hop Basics', self.levels[('Lindy Hop', 'Beginner')],
            ['Paulo', 'Teresa'], self.workshop_2session,
            [(2026, 9, 15, 19, 45, 20, 30), (2026, 9, 22, 19, 45, 20, 30)],
            description=(
                'Maybe you have already stumbled across a group of smiling '
                'people dancing somewhere around town, or seen a video of this '
                'joyful dance online, and wondered where to start. This '
                'workshop is exactly that first taste: the basic rhythm and a '
                'few simple steps, with the focus on feeling your partner\'s '
                'movement and that magic word behind every social dance -- '
                'connection. No previous experience needed. Just comfortable '
                'clothes, a bottle of water, and the will to try -- we take '
                'care of the rest.'
            ),
        )
        make_workshop(
            'HOP INto Tap', self.levels[('Tap', 'Beginner')],
            ['Gabriela', 'Luisa'], self.workshop_2session,
            [(2026, 9, 16, 18, 30, 19, 30), (2026, 9, 23, 18, 30, 19, 30)],
            description=(
                'When the body becomes a musical instrument and the feet turn '
                'into a percussion section, that is tap. Rhythm is the whole '
                'point: if the Nicholas Brothers, Fred Astaire or Eleanor '
                'Powell make you dream of another era, come try it. No '
                'previous experience needed -- just feet ready for uncharted '
                'waters. Step, stamp, tap, dig, shuffle, stomp, toe, brush...'
            ),
        )
        make_workshop(
            'HOP INto First Stops', self.levels[('Lindy Hop', 'Intermediate (1/2)')],
            ['Paulo', 'Teresa'], self.workshop_2session,
            [(2026, 9, 16, 19, 45, 21, 0), (2026, 9, 23, 19, 45, 21, 0)],
            description=(
                'Created in the spring of 1936 by Frankie Manning, one of the '
                'key figures of Lindy Hop, First Stops was the first '
                'choreography every regular at the Savoy Ballroom knew. As '
                'soon as the opening bars played, couples would organize '
                'themselves on the floor and dance it together. Some basic '
                'Lindy Hop steps are recommended before this workshop: swing '
                'out, circle, basic Charleston and tandem Charleston.'
            ),
        )
        make_workshop(
            'HOP INto Shag', self.levels[('Shag', 'Beginner')],
            ['Uriel', 'Katia'], self.workshop_2session,
            [(2026, 9, 17, 19, 45, 20, 30), (2026, 9, 24, 19, 45, 20, 30)],
            description=(
                'Collegiate Shag is one of the swing family styles, and '
                'certainly one of the most demanding -- danced to the fastest '
                'music of the bunch. Just when you thought Lindy Hop had '
                'enough energy... Jumps, kicks, a fast tempo and a healthy dose '
                'of chaos: this dance does not go unnoticed. No previous '
                'experience needed, just plenty of willingness to work up a '
                'sweat.'
            ),
        )
        # Single-session workshops. Exact time not specified in the source
        # sheet for either -- 19:45-20:45 used as a placeholder, matching
        # the usual weekday evening class slot.
        make_workshop(
            'HOP INto Shim Sham', self.levels[('Solo Jazz / Authentic Jazz', 'Beginner')],
            ['Ian'], self.workshop_1session,
            [(2026, 9, 10, 19, 45, 20, 45)],
            description=(
                'Some choreographies are part of swing\'s DNA -- the Shim Sham '
                'is one of them. A sequence of iconic steps created in the '
                '1930s and danced ever since by swing dancers everywhere, with '
                'small variations, plenty of personality and, inevitably, a '
                'smile on everyone\'s face. Learn it step by step and gain the '
                'confidence to dance it together with the whole room.'
            ),
        )
        make_workshop(
            # Source sheet: "until 11 September", no fixed date/venue on
            # file yet -- 9 September used as a placeholder; confirm before
            # publishing this one for real registrations. Tagged under
            # Lindy Hop (not Solo Jazz) since it is specifically about the
            # partnered "Follow" role, which only exists as a role on the
            # partnered dance types.
            'HOP INto Followers Choice', self.levels[('Lindy Hop', 'Intermediate (1/2)')],
            ['Marta'], self.workshop_1session,
            [(2026, 9, 9, 18, 30, 19, 30)],
            description=(
                'Who says following is just... following? This workshop turns '
                'that idea on its head and explores the follow role as an '
                'active, creative part of the dance, full of choices. '
                'Musicality, interpretation, styling, improvisation, and above '
                'all how to take what you receive from your partner and use it '
                'to make real-time decisions. For followers who want more '
                'autonomy, confidence and freedom on the floor.'
            ),
        )
        self.stdout.write('September 2026 workshops ok.')

    # ------------------------------------------------------------------
    # Events (Agenda sheet in "Eventos HOP IN")
    # ------------------------------------------------------------------
    def _make_events(self):
        def make_event(title, pricing, dt, duration_hours=3, description=''):
            slug = slugify('%s %s' % (title, dt.strftime('%Y-%m-%d')))
            if PublicEvent.objects.filter(slug=slug).exists():
                return PublicEvent.objects.get(slug=slug)
            e, created = PublicEvent.objects.get_or_create(
                title=title, slug=slug,
                defaults=dict(
                    status=Event.RegStatus.enabled,
                    location=self.cafe_ceuta,
                    pricingTier=pricing,
                    descriptionField=description,
                )
            )
            if created:
                EventOccurrence.objects.create(
                    event=e, startTime=dt, endTime=dt + timedelta(hours=duration_hours),
                )
                e.save()
            return e

        social_desc = (
            'Regular HOP IN social dance night at Cafe Ceuta -- come dance '
            'Lindy Hop, Solo Jazz and everything in between, no partner or '
            'experience required.'
        )
        social_dates = [
            (2026, 9, 2), (2026, 9, 16), (2026, 9, 30),
            (2026, 10, 14), (2026, 10, 28),
            (2026, 11, 11), (2026, 11, 25),
            (2026, 12, 9),
        ]
        for y, m, d in social_dates:
            make_event('HOP IN Social', self.social_free, aware(y, m, d, 21, 0), description=social_desc)

        jam_desc = (
            'HOP IN JAM: a social night with a live jam circle in the middle '
            'of the floor -- come dance, or just come watch.'
        )
        for y, m, d in [(2026, 9, 23), (2026, 11, 18)]:
            make_event('HOP IN JAM', self.jam_price, aware(y, m, d, 21, 0), description=jam_desc)

        # "Social, Workshop" combo evenings -- venue and price still TBD in
        # the source sheet, reusing Cafe Ceuta and the free tier as a
        # placeholder.
        hopout_desc = 'HOP OUT: a workshop followed by a social, outside the regular weekly schedule.'
        for y, m, d in [(2026, 11, 6), (2026, 12, 4)]:
            make_event('HOP OUT', self.social_free, aware(y, m, d, 20, 0), description=hopout_desc)

        # Bigger end-of-term party -- price and exact venue also TBD.
        make_event(
            'HOP IN Parties', self.social_free, aware(2026, 12, 19, 21, 0), duration_hours=4,
            description='End-of-term HOP IN party -- the bigger social night of the term.',
        )
        self.stdout.write('Events/socials ok.')

    # ------------------------------------------------------------------
    # Sample registrations: a few per event, mixing paid and pending
    # ------------------------------------------------------------------
    def _make_sample_registrations(self):
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            self.stdout.write(self.style.WARNING(
                'No superuser found - sample registrations skipped (run '
                'createsuperuser first).'
            ))
            return

        def register(event, role, first, last, email, price, paid):
            '''
            Creates a Registration + Invoice + EventRegistration directly
            (rather than driving the multi-step registration wizard), with
            the same end-state the real "pay at door" / "will pay at door"
            flows produce: a finalized Registration, and an Invoice either
            fully paid (collected by an admin/staff user, as at a door
            payment) or left unpaid with an outstanding balance (a
            commitment to pay at the door later).
            '''
            customer, _ = Customer.objects.get_or_create(
                first_name=first, last_name=last, email=email,
            )
            registration = Registration(
                payAtDoor=True,
                submissionUser=admin_user if paid else None,
                dateTime=self.now,
            )
            registration.save(
                submissionUser=admin_user, collectedByUser=admin_user if paid else None,
            )
            invoice = registration.invoice
            invoice.firstName = first
            invoice.lastName = last
            invoice.email = email
            invoice.grossTotal = price
            invoice.total = price
            invoice.status = Invoice.PaymentStatus.paid if paid else Invoice.PaymentStatus.unpaid
            invoice.amountPaid = price if paid else 0
            if paid:
                invoice.collectedByUser = admin_user
            invoice.save()

            # InvoiceItem.objects.create() is avoided here: on this install,
            # saving an InvoiceItem outside of the normal request/response
            # cycle triggers a post_save receiver chain (danceschool.core's
            # cache-invalidation / modified-date signals, and, when
            # danceschool.financial is installed, its RevenueItem creation)
            # that silently rolls back the whole insert -- no exception is
            # raised, but the row is simply not there afterwards (reproduced
            # directly in the shell; root cause not fully isolated, but
            # consistently and only affects this specific model's .save()).
            # bulk_create() bypasses .save() and all signals entirely, which
            # sidesteps the issue (and is fine here: RevenueItem bookkeeping
            # from the optional financial app is out of scope for demo data).
            invoice_item = InvoiceItem.objects.bulk_create([InvoiceItem(
                invoice=invoice, description=str(event), grossTotal=price, total=price,
            )])[0]
            er = EventRegistration.objects.create(
                registration=registration, event=event, customer=customer,
                role=role, invoiceItem=invoice_item,
            )
            er.occurrences.set(event.eventoccurrence_set.all())
            er.save()

            registration.finalize()

        # A handful of fictional test customers -- clearly demo data, not
        # real HOP IN members.
        beginner_lindy = Series.objects.filter(classDescription__title='Beginner Lindy Hop').first()
        if beginner_lindy:
            register(beginner_lindy, self.lead, 'Rita', 'Almeida', 'rita.almeida@example.com',
                     self.pares.onlinePrice, paid=True)
            register(beginner_lindy, self.follow, 'Bruno', 'Teixeira', 'bruno.teixeira@example.com',
                     self.pares.onlinePrice, paid=False)

        lindy_basics_ws = Series.objects.filter(classDescription__title='HOP INto Lindy Hop Basics').first()
        if lindy_basics_ws:
            register(lindy_basics_ws, self.follow, 'Sofia', 'Martins', 'sofia.martins@example.com',
                     self.workshop_2session.onlinePrice, paid=True)
            register(lindy_basics_ws, self.lead, 'Diogo', 'Rocha', 'diogo.rocha@example.com',
                     self.workshop_2session.onlinePrice, paid=False)

        solo_basics_ws = Series.objects.filter(classDescription__title='HOP INto Solo Basics').first()
        if solo_basics_ws:
            register(solo_basics_ws, self.solo_role, 'Beatriz', 'Lopes', 'beatriz.lopes@example.com',
                     self.workshop_2session.onlinePrice, paid=True)

        jam = PublicEvent.objects.filter(title='HOP IN JAM').order_by('eventoccurrence__startTime').first()
        if jam:
            register(jam, None, 'Miguel', 'Santos', 'miguel.santos@example.com',
                     self.jam_price.onlinePrice, paid=True)
            register(jam, None, 'Carolina', 'Neves', 'carolina.neves@example.com',
                     self.jam_price.onlinePrice, paid=False)

        social = PublicEvent.objects.filter(title='HOP IN Social').order_by('eventoccurrence__startTime').first()
        if social:
            register(social, None, 'Tiago', 'Oliveira', 'tiago.oliveira@example.com', 0, paid=True)

        self.stdout.write('Sample registrations ok (mix of paid and pending).')


if __name__ == '__main__':
    Command().handle()
