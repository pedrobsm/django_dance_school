"""
Creates sample data for the HOP IN association: dance types, levels,
class descriptions, pricing, locations, instructors, a handful of class
series (past, ongoing and future), and one social event.

Safe to run more than once: uses get_or_create wherever practical.

Usage:
    python3 manage.py create_demo_data
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from danceschool.core.constants import getConstant
from danceschool.core.models import (
    ClassDescription, DanceRole, DanceType, DanceTypeLevel, Event,
    EventOccurrence, EventStaffMember, Instructor, Location, PricingTier,
    PublicEvent, Series, StaffMember,
)


class Command(BaseCommand):
    help = 'Creates sample/demo data so you can see the site working without manual data entry.'

    def handle(self, *args, **options):
        now = timezone.now()

        # --- Roles ---
        lead, _ = DanceRole.objects.get_or_create(name='Lead', defaults={'order': 1})
        follow, _ = DanceRole.objects.get_or_create(name='Follow', defaults={'order': 2})
        self.stdout.write('Roles ok.')

        # --- Dance types ---
        lindy, _ = DanceType.objects.get_or_create(name='Lindy Hop', defaults={'order': 1})
        lindy.roles.set([lead, follow])
        blues, _ = DanceType.objects.get_or_create(name='Blues', defaults={'order': 2})
        blues.roles.set([lead, follow])
        self.stdout.write('Dance types ok.')

        # --- Levels ---
        levels = {}
        for dt, names in [(lindy, ['Iniciacao', 'Intermedio']), (blues, ['Iniciacao'])]:
            for i, name in enumerate(names, start=1):
                lvl, _ = DanceTypeLevel.objects.get_or_create(
                    name=name, danceType=dt, defaults={'order': i}
                )
                levels[(dt.name, name)] = lvl
        self.stdout.write('Levels ok.')

        # --- Class descriptions ---
        class_specs = [
            ('Lindy Hop - Iniciacao', 'Aprende os passos base do Lindy Hop num ambiente descontraido.', levels[('Lindy Hop', 'Iniciacao')]),
            ('Lindy Hop - Intermedio', 'Para quem ja domina o basico e quer evoluir.', levels[('Lindy Hop', 'Intermedio')]),
            ('Blues - Iniciacao', 'Introducao a danca de Blues, movimento e conexao.', levels[('Blues', 'Iniciacao')]),
        ]
        descriptions = []
        for title, desc, level in class_specs:
            cd, _ = ClassDescription.objects.get_or_create(
                title=title, danceTypeLevel=level,
                defaults={'description': desc, 'slug': slugify(title)}
            )
            descriptions.append(cd)
        self.stdout.write('Class descriptions ok.')

        # --- Pricing ---
        pricing, _ = PricingTier.objects.get_or_create(
            name='Mensalidade Standard',
            defaults={'onlinePrice': 40, 'doorPrice': 45, 'dropinPrice': 12}
        )
        self.stdout.write('Pricing ok.')

        # --- Locations ---
        loc1, _ = Location.objects.get_or_create(
            name='Estudio HOP IN - Bonfim',
            defaults=dict(
                status=Location.StatusChoices.active,
                address='Rua de Exemplo 123', city='Porto', state='Porto',
                zip='4300-001', directions='Perto do metro do Bonfim.',
                defaultCapacity=40,
            )
        )
        loc2, _ = Location.objects.get_or_create(
            name='Salao HOP IN - Centro',
            defaults=dict(
                status=Location.StatusChoices.active,
                address='Rua Central 45', city='Porto', state='Porto',
                zip='4000-001', directions='No centro da cidade.',
                defaultCapacity=80,
            )
        )
        self.stdout.write('Locations ok.')

        # --- Instructors ---
        instructors_data = [
            ('Maria', 'Silva', 'maria@hopin.pt', 'Instrutora principal de Lindy Hop.'),
            ('Joao', 'Santos', 'joao@hopin.pt', 'Instrutor de Blues.'),
            ('Ana', 'Costa', 'ana@hopin.pt', 'Instrutora convidada.'),
        ]
        instructors = []
        for first, last, email, bio in instructors_data:
            sm, _ = StaffMember.objects.get_or_create(
                firstName=first, lastName=last,
                defaults=dict(publicEmail=email, privateEmail=email, bio=bio)
            )
            Instructor.objects.get_or_create(
                staffMember=sm, defaults={'status': Instructor.InstructorStatus.roster}
            )
            instructors.append(sm)
        self.stdout.write('Instructors ok.')

        # --- Class series (past, ongoing, future) ---
        series_specs = [
            dict(classDescription=descriptions[0], location=loc1, start_offset_days=-30, weeks=4, instructor=instructors[0]),
            dict(classDescription=descriptions[1], location=loc1, start_offset_days=-7, weeks=6, instructor=instructors[0]),
            dict(classDescription=descriptions[2], location=loc2, start_offset_days=7, weeks=6, instructor=instructors[1]),
        ]
        instructor_category = getConstant('general__eventStaffCategoryInstructor')
        for spec in series_specs:
            exists = Series.objects.filter(
                classDescription=spec['classDescription'], location=spec['location']
            ).exists()
            if exists:
                continue
            s = Series(
                classDescription=spec['classDescription'],
                pricingTier=pricing,
                location=spec['location'],
                status=Event.RegStatus.enabled,
            )
            s.save()
            start = now + timedelta(days=spec['start_offset_days'])
            for w in range(spec['weeks']):
                EventOccurrence.objects.create(
                    event=s,
                    startTime=start + timedelta(weeks=w),
                    endTime=start + timedelta(weeks=w, hours=1, minutes=30),
                )
            ssm = EventStaffMember.objects.create(
                event=s, category=instructor_category, staffMember=spec['instructor'],
            )
            ssm.occurrences.set(s.eventoccurrence_set.all())
            ssm.save()
            s.save()
        self.stdout.write('Class series ok.')

        # --- A social event / party ---
        try:
            party, created = PublicEvent.objects.get_or_create(
                title='Social de Swing & Blues',
                defaults=dict(
                    slug='social-swing-blues',
                    status=Event.RegStatus.enabled,
                    location=loc2,
                    pricingTier=pricing,
                )
            )
            if created:
                EventOccurrence.objects.create(
                    event=party,
                    startTime=now + timedelta(days=14, hours=20),
                    endTime=now + timedelta(days=14, hours=23),
                )
                party.save()
            self.stdout.write('Social event ok.')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Nao foi possivel criar o evento social: {e}'))

        self.stdout.write(self.style.SUCCESS('Dados de demonstracao criados com sucesso.'))
