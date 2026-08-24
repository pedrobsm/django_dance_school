"""
Creates dummy data modelled closely on the HOP IN association's real 2025/26
teaching plan and September 2026 workshops (as planned in the association's
internal spreadsheet and workshop docs), plus a homepage built from the
association's brand manifesto.

This is a PoC: names, exact levels and minor scheduling details have been
simplified/approximated where the source material was ambiguous or still
undecided. Safe to run more than once: uses get_or_create wherever
practical; the Professores/Turmas CMS pages are skipped (not duplicated)
if a page with the same title already exists, and the homepage manifesto
content is written into whichever page is already set as the site's
homepage (e.g. one created by setupschool) rather than creating a second
homepage-like page — re-running this command overwrites that page's
splash_caption/content placeholders with the manifesto text again, so it
always converges instead of piling up duplicate plugins.

Complements (does not replace) create_demo_data: reuses the same Locations
and Lead/Follow DanceRole by name, so running both is safe.

Usage:
    python3 manage.py create_hopin_demo_data
"""
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from danceschool.core.constants import getConstant
from danceschool.core.models import (
    ClassDescription, DanceRole, DanceType, DanceTypeLevel, Event,
    EventOccurrence, EventStaffMember, Instructor, Location, PricingTier,
    Series, StaffMember,
)


def aware(y, m, d, hh, mm):
    return timezone.make_aware(datetime(y, m, d, hh, mm))


class Command(BaseCommand):
    help = (
        'Creates dummy data modelled on the HOP IN 2025/26 teaching plan and '
        'September 2026 workshops, plus a homepage from the brand manifesto.'
    )

    def handle(self, *args, **options):
        # --- Roles ---
        lead, _ = DanceRole.objects.get_or_create(name='Lead', defaults={'order': 1})
        follow, _ = DanceRole.objects.get_or_create(name='Follow', defaults={'order': 2})
        solo_role, _ = DanceRole.objects.get_or_create(
            name='Dancarino(a)', defaults={'pluralName': 'Dancarinos(as)', 'order': 3}
        )
        self.stdout.write('Roles ok.')

        # --- Dance types & levels ---
        lindy, _ = DanceType.objects.get_or_create(name='Lindy Hop', defaults={'order': 1})
        lindy.roles.set([lead, follow])
        jazz, _ = DanceType.objects.get_or_create(name='Solo Jazz / Authentic Jazz', defaults={'order': 2})
        jazz.roles.set([solo_role])
        tap, _ = DanceType.objects.get_or_create(name='Tap', defaults={'order': 3})
        tap.roles.set([solo_role])
        shag, _ = DanceType.objects.get_or_create(name='Shag', defaults={'order': 4})
        shag.roles.set([lead, follow])

        levels = {}
        level_specs = [
            (lindy, ['Iniciacao', '1/2', '3', 'Training']),
            (jazz, ['Iniciacao', '1/2', '3']),
            (tap, ['Iniciacao']),
            (shag, ['Iniciacao']),
        ]
        for dt, names in level_specs:
            for i, name in enumerate(names, start=1):
                lvl, _ = DanceTypeLevel.objects.get_or_create(
                    name=name, danceType=dt, defaults={'order': i}
                )
                levels[(dt.name, name)] = lvl
        self.stdout.write('Dance types & levels ok.')

        # --- Locations (shared with create_demo_data.py by name) ---
        bonfim, _ = Location.objects.get_or_create(
            name='Estudio HOP IN - Bonfim',
            defaults=dict(
                status=Location.StatusChoices.active,
                address='Rua de Exemplo 123', city='Porto', state='Porto',
                zip='4300-001', directions='Perto do metro do Bonfim.',
                defaultCapacity=40,
            )
        )
        centro, _ = Location.objects.get_or_create(
            name='Salao HOP IN - Centro',
            defaults=dict(
                status=Location.StatusChoices.active,
                address='Rua Central 45', city='Porto', state='Porto',
                zip='4000-001', directions='No centro da cidade.',
                defaultCapacity=80,
            )
        )
        self.stdout.write('Locations ok.')

        # --- Instructors (from the teachers named in the 2025/26 plan) ---
        instructors_data = [
            ('Teresa', 'Nogueira', 'Lindy Hop e Solo Jazz. Da-nos as boas-vindas nas turmas de iniciacao.'),
            ('Paulo', 'Ferreira', 'Lindy Hop e Solo Jazz. Parceiro habitual da Teresa nas turmas de iniciacao.'),
            ('Gabriela', 'Marques', 'Solo Jazz / Authentic Jazz e Tap.'),
            ('Luisa', 'Pinto', 'Lindy Hop e Tap. Tambem orienta a Training Class.'),
            ('Ian', 'Cardoso', 'Lindy Hop, turmas avancadas.'),
            ('Mariana', 'Sousa', 'Lindy Hop. Orienta a Training Class.'),
            ('Uriel', 'Duarte', 'Shag.'),
            ('Katia', 'Ramos', 'Shag.'),
            ('Ines', 'Carvalho', 'Lindy Hop. Orienta a Training Class.'),
            ('Sonia', 'Armoza', 'Danca Oriental (convidada).'),
        ]
        instr = {}
        for first, last, bio in instructors_data:
            sm, _ = StaffMember.objects.get_or_create(
                firstName=first, lastName=last,
                defaults=dict(bio=bio)
            )
            Instructor.objects.get_or_create(
                staffMember=sm, defaults={'status': Instructor.InstructorStatus.roster}
            )
            instr[first] = sm
        self.stdout.write('Instructors ok.')

        # --- Pricing (from the "Mes / Trimestre" pricing table) ---
        pares, _ = PricingTier.objects.get_or_create(
            name='Mensalidade Modulo - Par',
            defaults={'onlinePrice': 30, 'doorPrice': 35, 'dropinPrice': 10}
        )
        solo, _ = PricingTier.objects.get_or_create(
            name='Mensalidade Modulo - Solo',
            defaults={'onlinePrice': 25, 'doorPrice': 30, 'dropinPrice': 8}
        )
        workshop_price, _ = PricingTier.objects.get_or_create(
            name='Workshop HOP INto',
            defaults={'onlinePrice': 25, 'doorPrice': 30, 'dropinPrice': 15}
        )
        self.stdout.write('Pricing ok.')

        instructor_category = getConstant('general__eventStaffCategoryInstructor')

        def make_series(title, level, location, pricing, teachers, weeks, start, description=''):
            '''Creates a ClassDescription + Series with weekly occurrences, if not already present.'''
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
                    event=s, category=instructor_category, staffMember=instr[t],
                )
                ssm.occurrences.set(s.eventoccurrence_set.all())
                ssm.save()
            s.save()

        def make_workshop(title, level, location, teachers, dates_times, description=''):
            '''
            dates_times: list of (year, month, day, start_hour, start_min, end_hour, end_min)
            for each session (workshops here run 2 sessions).
            '''
            cd, _ = ClassDescription.objects.get_or_create(
                title=title, danceTypeLevel=level,
                defaults={'description': description, 'slug': slugify(title)}
            )
            if Series.objects.filter(classDescription=cd, location=location).exists():
                return
            s = Series(
                classDescription=cd, pricingTier=workshop_price, location=location,
                status=Event.RegStatus.enabled, allowDropins=True,
            )
            s.save()
            for (y, m, d, sh, sm_, eh, em) in dates_times:
                EventOccurrence.objects.create(
                    event=s, startTime=aware(y, m, d, sh, sm_), endTime=aware(y, m, d, eh, em),
                )
            for t in teachers:
                ssm = EventStaffMember.objects.create(
                    event=s, category=instructor_category, staffMember=instr[t],
                )
                ssm.occurrences.set(s.eventoccurrence_set.all())
                ssm.save()
            s.save()

        # --- Regular season classes (2025/26 "TO-BE" schedule, first module Out-Dez) ---
        # Weekly start dates use the coming Tuesday/Wednesday/Friday from "now" as a stand-in
        # for the real October 2026 season start.
        now = timezone.now()

        def next_weekday(base, weekday):
            '''weekday: Monday=0 ... Sunday=6'''
            days_ahead = (weekday - base.weekday()) % 7
            days_ahead = days_ahead or 7
            return base + timedelta(days=days_ahead)

        tue_1830 = next_weekday(now, 1).replace(hour=18, minute=30, second=0, microsecond=0)
        tue_1945 = tue_1830.replace(hour=19, minute=45)
        tue_2115 = tue_1830.replace(hour=21, minute=15)
        wed_1830 = next_weekday(now, 2).replace(hour=18, minute=30, second=0, microsecond=0)
        wed_1945 = wed_1830.replace(hour=19, minute=45)
        fri_1830 = next_weekday(now, 4).replace(hour=18, minute=30, second=0, microsecond=0)
        fri_1945 = fri_1830.replace(hour=19, minute=45)

        make_series(
            'Iniciacao Authentic Jazz', levels[('Solo Jazz / Authentic Jazz', 'Iniciacao')], bonfim,
            solo, ['Teresa', 'Paulo'], weeks=12, start=tue_1830,
            description=(
                'Turma trimestral de iniciacao ao Authentic Jazz. Sequencias simples '
                'criadas pelos professores, passos base (ver lista do Chester) e '
                'coreografias historicas como Shim Sham e Jitterbug Stroll.'
            ),
        )
        make_series(
            'Iniciacao Lindy Hop', levels[('Lindy Hop', 'Iniciacao')], bonfim,
            pares, ['Teresa', 'Paulo'], weeks=12, start=tue_1945,
            description=(
                'Turma trimestral de iniciacao ao Lindy Hop. Groove walk e Triple Step, '
                'em dinamicas de 6 e 8 tempos.'
            ),
        )
        make_series(
            'Training Class Lindy Hop', levels[('Lindy Hop', 'Training')], bonfim,
            pares, ['Mariana', 'Ines', 'Luisa'], weeks=12, start=tue_2115,
            description='Turma de treino orientada, para bailarinos que ja dominam o Lindy Hop.',
        )
        make_series(
            'Authentic Jazz - Turma Avancada', levels[('Solo Jazz / Authentic Jazz', '3')], centro,
            solo, ['Gabriela'], weeks=4, start=wed_1830,
            description='Modulo tematico mensal, com professores em rotacao ao longo do ano.',
        )
        make_series(
            'Lindy Hop - Turma Avancada', levels[('Lindy Hop', '3')], centro,
            pares, ['Ian', 'Luisa', 'Mariana'], weeks=4, start=wed_1945,
            description='Modulo tematico: Swing Out Lab - refinar o Swing Out e variacoes.',
        )
        make_series(
            'Authentic Jazz - Modulos Tematicos', levels[('Solo Jazz / Authentic Jazz', '1/2')], bonfim,
            solo, ['Gabriela', 'Paulo'], weeks=4, start=fri_1830,
            description='Modulo tematico mensal: Shim Sham variacao 1 (Al and Leon).',
        )
        make_series(
            'Lindy Hop - Modulos Tematicos', levels[('Lindy Hop', '1/2')], bonfim,
            pares, ['Gabriela', 'Paulo'], weeks=4, start=fri_1945,
            description='Modulo tematico mensal: Swing Out Lab - refinar o Swing Out e variacoes.',
        )
        self.stdout.write('Turmas regulares 2025/26 ok.')

        # --- September 2026 workshops ("HOP INto...", real dates/prices/teachers) ---
        make_workshop(
            'HOP INto Solo Basics', levels[('Solo Jazz / Authentic Jazz', 'Iniciacao')], bonfim,
            ['Teresa'],
            [(2026, 9, 15, 18, 30, 19, 30), (2026, 9, 22, 18, 30, 19, 30)],
            description=(
                'Swing. Um estilo musical em que, automaticamente, o pezinho comeca a bater '
                'e a acompanhar o ritmo, e o corpo quer mexer. Mas... como? Sim, e possivel '
                'dancar ao som de jazz, brincar com os seus ritmos e contratempos, e ser a '
                'forma visivel desta forma de arte. Com passos iconicos como fall off the '
                'log, shoe-shine, scarecrow, drunk sailor, naturalmente e uma danca para '
                'gente que nao se leva demasiado a serio. Intrigad@? Vem descobrir por ti '
                'propri@!'
            ),
        )
        make_workshop(
            'HOP INto Lindy Hop Basics', levels[('Lindy Hop', 'Iniciacao')], bonfim,
            ['Paulo', 'Teresa'],
            [(2026, 9, 15, 19, 45, 20, 30), (2026, 9, 22, 19, 45, 20, 30)],
            description=(
                'Ola! Talvez ja tenhas tropecado num grupinho de gente sorridente a dancar '
                'pela cidade, ou viste uns videos desta danca alegre em qualquer plataforma. '
                'Ficaste com vontade de experimentar e nao sabes por onde comecar? '
                'Organizamos esta oficina para uma primeira prova. Experimentar o ritmo base '
                'e passos simples, focando sobretudo em sentir o movimento do par com que '
                'estas a dancar e nessa palavra magica, fundamento das dancas sociais - '
                'conexao. Nao e preciso qualquer experiencia previa. So roupa confortavel, '
                'uma garrafa de agua e... vontade! Nos tratamos do resto.'
            ),
        )
        make_workshop(
            'HOP INto Tap', levels[('Tap', 'Iniciacao')], bonfim,
            ['Gabriela', 'Luisa'],
            [(2026, 9, 16, 18, 30, 19, 30), (2026, 9, 23, 18, 30, 19, 30)],
            description=(
                'Quando fazemos do corpo um instrumento musical, e transformamos os nossos '
                'pes numa desenhada percussao - ai temos o sapateado. O ritmo como foco! Se '
                'o estilo dos Nicolas brothers ou Fred Astaire e Eleanor Powell te inspiram e '
                'fazem sonhar com outras eras... vem daí! Nesta oficina vamos experimentar '
                'alguns dos passos base, e perceber como cabe todo um mundo no encontro entre '
                'dois pes e um chao. Step, stamp, tap, dig, shuffle, stomp, toe, brush... Nao '
                'e preciso experiencia previa. So uns pes preparados para mares nunca dantes '
                'navegados. Atreves-te?'
            ),
        )
        make_workshop(
            'HOP INto First Stops', levels[('Lindy Hop', '1/2')], bonfim,
            ['Paulo', 'Teresa'],
            [(2026, 9, 16, 19, 45, 21, 0), (2026, 9, 23, 19, 45, 21, 0)],
            description=(
                'Inventada na primavera de 1936 por uma das figuras chave do Lindy Hop, '
                'Frankie Manning, e a primeira das coreografias que todos quantos '
                'frequentavam o Savoy conheciam. Inspirada pela musica de Jimmie Lunceford, '
                'assim que se ouviam os primeiros acordes os varios pares organizavam-se na '
                'pista e faziam-na em simultaneo. Porque a historia as vezes nao esta nos '
                'museus, e pode continuar a viver-se - dancando. Queres vir aprender '
                'connosco? Para esta oficina aconselhamos a que saibas alguns passos basicos '
                'do lindy hop, como swing out, circle, base de charleston e tandem '
                'charleston.'
            ),
        )
        make_workshop(
            'HOP INto Shag', levels[('Shag', 'Iniciacao')], bonfim,
            ['Uriel', 'Katia'],
            [(2026, 9, 17, 19, 45, 20, 30), (2026, 9, 24, 19, 45, 20, 30)],
            description=(
                'O Collegiate Shag e um dos estilos de danca swing, e certamente um dos mais '
                'desafiantes. Dancado ao som das musicas mais rapidas, e energetico e cheio '
                'de boa disposicao. Nao e preciso experiencia previa - so muita vontade de '
                'suar a camisola!'
            ),
        )
        self.stdout.write('Workshops de Setembro 2026 ok.')

        # --- Homepage with the HOP IN brand manifesto (condensed) ---
        self._create_cms_pages()

        self.stdout.write(self.style.SUCCESS('Dados HOP IN criados com sucesso.'))

    def _create_cms_pages(self):
        from cms.api import add_plugin, create_page, publish_page
        from cms.models import CMSPlugin, Page

        this_user = User.objects.filter(is_superuser=True).first()
        if not this_user:
            self.stdout.write(self.style.WARNING(
                'Sem superuser: paginas CMS nao foram criadas. Corre createsuperuser primeiro.'
            ))
            return

        language = 'en'  # only language configured in LANGUAGES; content itself is in Portuguese.

        # Reuse whatever page is already the homepage (e.g. created by
        # setupschool) instead of creating a second one — only create a new
        # page if the site genuinely has no homepage yet. This deliberately
        # does not touch the existing page's title/menu_title/slug, only its
        # placeholders, so it works whether "Home", "HOP IN", or anything
        # else is already set as homepage.
        home_page = Page.objects.filter(is_home=True, publisher_is_draft=True).first()
        if not home_page:
            home_page = create_page(
                'HOP IN', 'cms/frontpage.html', language,
                menu_title='Inicio', in_navigation=True, published=True,
            )
            home_page.set_as_homepage()

        manifesto_body = (
            '<p><strong>Mais do que aprender a dancar.</strong></p>'
            '<p>A HOP IN e uma comunidade de swing e blues no Porto. Queremos '
            'construir mais do que um lugar para aprender a dancar: um lugar onde '
            'se descobre o swing, se cresce ao proprio ritmo, se fazem amizades e '
            'se encontra uma comunidade da qual apetece fazer parte.</p>'
            '<h2>Para quem esta a comecar... e para quem quer ir mais longe</h2>'
            '<p>A HOP IN nao e so a porta de entrada para quem nunca dancou - e '
            'tambem espaco para quem ja danca, quer aprofundar, experimentar coisas '
            'novas e descobrir ate onde pode levar a sua danca. <em>Descobrir - '
            'Aprender - Experimentar - Evoluir - Participar</em> - cada pessoa entra '
            'num ponto diferente e escolhe o seu proximo passo.</p>'
            '<h2>Escola + Eventos</h2>'
            '<p>A escola cria oportunidades para <strong>aprender e evoluir</strong> '
            '- aulas, workshops, treino, musicalidade. A associacao cria '
            'oportunidades para <strong>participar</strong> - sociais, jams, '
            'festivais, voluntariado. E nesta combinacao que se encontra a HOP '
            'IN.</p>'
            '<p class="text-center"><strong>Warm &middot; Welcoming &middot; '
            'Playful &middot; Friendly &middot; Curious</strong></p>'
        )
        caption_body = '<p class="lead text-white text-center">Aprende. Experimenta. Danca.</p>'

        # Placeholders on the reused page depend on its template; only
        # splash_caption exists on cms/frontpage.html, 'content' exists on
        # both frontpage.html and home.html.
        for slot, body in [('splash_caption', caption_body), ('content', manifesto_body)]:
            placeholder = home_page.placeholders.filter(slot=slot).first()
            if not placeholder:
                continue
            # Clear whatever is already there (default setupschool "Welcome"
            # text, or our own content from a previous run) so re-running
            # this command always converges on the manifesto, without piling
            # up duplicate plugins in the same placeholder.
            CMSPlugin.objects.filter(placeholder=placeholder, language=language).delete()
            add_plugin(placeholder, 'TextPlugin', language, body=body)

        publish_page(home_page, this_user, language)
        self.stdout.write('Pagina inicial (manifesto) atualizada.')

        if not Page.objects.filter(title_set__title='Professores').exists():
            instructor_page = create_page(
                'Professores', 'cms/twocolumn_rightsidebar.html', language,
                menu_title='Professores', in_navigation=True, published=True,
            )
            content_placeholder = instructor_page.placeholders.get(slot='content')
            add_plugin(
                content_placeholder, 'StaffMemberListPlugin', language,
                template='core/staff_list.html',
                # Explicitly empty: the field's non-empty MultiSelectField default
                # triggers a django-multiselectfield bug where `instructor__status__in`
                # against the stored MSFList produces an EmptyResultSet (0 instructors
                # shown), instead of the plain-list .exclude() branch that runs when
                # this field is falsy. See CLAUDE.md pitfall list.
                statusChoices=[],
            )
            publish_page(instructor_page, this_user, language)
            self.stdout.write('Pagina de professores criada.')
        else:
            self.stdout.write('Pagina de professores ja existia, nao foi recriada.')

        if not Page.objects.filter(title_set__title='Turmas').exists():
            calendar_page = create_page(
                'Turmas', 'cms/home.html', language,
                menu_title='Turmas', in_navigation=True, published=True,
            )
            content_placeholder = calendar_page.placeholders.get(slot='content')
            add_plugin(content_placeholder, 'PublicCalendarPlugin', language)
            publish_page(calendar_page, this_user, language)
            self.stdout.write('Pagina de turmas/calendario criada.')
        else:
            self.stdout.write('Pagina de turmas ja existia, nao foi recriada.')
