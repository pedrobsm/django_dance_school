# -*- coding: utf-8 -*-
"""
Cria/atualiza as traducoes PT das paginas do django-cms.

Contexto: as paginas foram todas criadas quando o site so tinha um idioma
configurado ('en'), por isso o conteudo em portugues ficou guardado no slot
ingles. Este comando poe cada pagina a existir nos dois idiomas:

  - garante um titulo/slug PT para cada pagina (mapa PAGE_MAP abaixo);
  - copia o conteudo dos placeholders EN -> PT quando o lado PT esta vazio;
  - corrige os titulos EN que estavam em portugues;
  - substitui o texto PT que ficou no slot EN da homepage por uma versao
    inglesa, para um visitante em /en/ nao apanhar a pagina em portugues;
  - publica os dois idiomas.

E idempotente: correr mais do que uma vez converge para o mesmo estado e nao
duplica paginas nem plugins.

Uso:  python3 manage.py translate_cms_pages
"""
from django.core.management.base import BaseCommand
from django.db import transaction


SRC_LANG = 'en'
DST_LANG = 'pt'

# Chave: slug da pagina no idioma de origem (identificador estavel).
# Valores: titulos/slug a aplicar em cada idioma.
#   en_title=None  -> deixa o titulo ingles como esta
#
# Nota: nao mexemos nos *slugs* ingleses de proposito. As paginas criadas
# pelo create_hopin_demo_data ficaram com slug portugues ('professores',
# 'turmas') tambem em ingles; mudar o slug muda o URL e nao vale o risco
# num PoC. So corrigimos o titulo visivel.
PAGE_MAP = {
    'home': {
        'pt_title': 'Inicio', 'pt_menu': 'Inicio', 'pt_slug': 'inicio',
    },
    'hop-in': {
        'pt_title': 'HOP IN', 'pt_menu': 'Inicio', 'pt_slug': 'hop-in',
    },
    'professores': {
        'en_title': 'Instructors', 'en_menu': 'Instructors',
        'pt_title': 'Professores', 'pt_menu': 'Professores', 'pt_slug': 'professores',
    },
    'turmas': {
        'en_title': 'Classes', 'en_menu': 'Classes',
        'pt_title': 'Turmas', 'pt_menu': 'Turmas', 'pt_slug': 'turmas',
    },
    'register': {
        'pt_title': 'Inscricoes', 'pt_menu': 'Inscricoes', 'pt_slug': 'inscricoes',
    },
    'calendar': {
        'pt_title': 'Calendario', 'pt_menu': 'Calendario', 'pt_slug': 'calendario',
    },
    'frequently-asked-questions': {
        'pt_title': 'Perguntas Frequentes', 'pt_menu': 'Perguntas Frequentes',
        'pt_slug': 'perguntas-frequentes',
    },
    'latest-news': {
        'pt_title': 'Noticias', 'pt_menu': 'Noticias', 'pt_slug': 'noticias',
    },
    'stats': {
        'pt_title': 'Estatisticas da Escola', 'pt_menu': 'Estatisticas',
        'pt_slug': 'estatisticas',
    },
    'login': {
        'pt_title': 'Entrar', 'pt_menu': 'Entrar', 'pt_slug': 'entrar',
    },
    'profile': {
        'pt_title': 'A Minha Conta', 'pt_menu': 'A Minha Conta', 'pt_slug': 'a-minha-conta',
    },
    'logout': {
        'pt_title': 'Sair', 'pt_menu': 'Sair', 'pt_slug': 'sair',
    },
}

# Versao inglesa do manifesto que o create_hopin_demo_data escreve em
# portugues. Traducao do texto que ja existe, nao copy nova — deve ser
# revista por alguem da HOP IN antes de sair do PoC.
HOME_EN_BODY = (
    '<p><strong>More than learning to dance.</strong></p>'
    '<p>HOP IN is a swing and blues community in Porto. We want to build more '
    'than a place to learn how to dance: a place where you discover swing, grow '
    'at your own pace, make friends and find a community you want to be part '
    'of.</p>'
    '<h2>For those just starting out... and those who want to go further</h2>'
    '<p>HOP IN is not only the way in for people who have never danced - it is '
    'also a space for those who already dance and want to go deeper, try new '
    'things and find out how far their dancing can take them. <em>Discover - '
    'Learn - Experiment - Evolve - Take part</em> - everyone starts at a '
    'different point and chooses their own next step.</p>'
    '<h2>School + Events</h2>'
    '<p>The school creates opportunities to <strong>learn and grow</strong> - '
    'classes, workshops, training, musicality. The association creates '
    'opportunities to <strong>take part</strong> - socials, jams, festivals, '
    'volunteering. HOP IN lives in that combination.</p>'
    '<p class="text-center"><strong>Warm &middot; Welcoming &middot; '
    'Playful &middot; Friendly &middot; Curious</strong></p>'
)
HOME_EN_CAPTION = '<p class="lead text-white text-center">Learn. Experiment. Dance.</p>'


class Command(BaseCommand):
    help = 'Cria/atualiza as traducoes PT das paginas do django-cms.'

    @transaction.atomic
    def handle(self, *args, **options):
        from cms.api import add_plugin, create_title
        from cms.models import CMSPlugin, Page, StaticPlaceholder, Title
        from cms.utils.copy_plugins import copy_plugins_to

        pages = Page.objects.filter(publisher_is_draft=True)
        if not pages.exists():
            self.stdout.write(self.style.WARNING('Nao ha paginas CMS. Nada a fazer.'))
            return

        created = updated = copied = 0

        for page in pages:
            src = Title.objects.filter(page=page, language=SRC_LANG).first()
            if not src:
                self.stdout.write(
                    'Pagina %s sem titulo %s, ignorada.' % (page.pk, SRC_LANG)
                )
                continue

            cfg = PAGE_MAP.get(src.slug, {})

            # --- 1. Corrigir titulo EN que estava em portugues ---
            if cfg.get('en_title') and src.title != cfg['en_title']:
                src.title = cfg['en_title']
                src.menu_title = cfg.get('en_menu') or cfg['en_title']
                src.save()
                updated += 1
                self.stdout.write('EN: %s -> %s' % (src.slug, cfg['en_title']))

            # --- 2. Garantir titulo PT ---
            dst = Title.objects.filter(page=page, language=DST_LANG).first()
            pt_title = cfg.get('pt_title') or src.title
            pt_menu = cfg.get('pt_menu') or pt_title
            pt_slug = cfg.get('pt_slug') or src.slug

            if not dst:
                create_title(
                    language=DST_LANG, title=pt_title, page=page,
                    menu_title=pt_menu, slug=pt_slug,
                )
                created += 1
                self.stdout.write(self.style.SUCCESS(
                    'PT criado: %s (%s)' % (pt_title, pt_slug)
                ))
            elif dst.title != pt_title or dst.menu_title != pt_menu:
                dst.title = pt_title
                dst.menu_title = pt_menu
                dst.save()
                updated += 1
                self.stdout.write('PT atualizado: %s' % pt_title)

            # --- 3. Copiar conteudo dos placeholders EN -> PT ---
            for placeholder in page.placeholders.all():
                if placeholder.get_plugins_list(language=DST_LANG):
                    continue  # ja tem conteudo PT, nao sobrepomos
                src_plugins = placeholder.get_plugins_list(language=SRC_LANG)
                if not src_plugins:
                    continue
                copy_plugins_to(src_plugins, placeholder, to_language=DST_LANG)
                copied += 1

            # --- 4. Homepage: por a versao inglesa no slot EN ---
            if page.is_home:
                for slot, body in (
                    ('splash_caption', HOME_EN_CAPTION),
                    ('content', HOME_EN_BODY),
                ):
                    placeholder = page.placeholders.filter(slot=slot).first()
                    if not placeholder:
                        continue
                    CMSPlugin.objects.filter(
                        placeholder=placeholder, language=SRC_LANG
                    ).delete()
                    add_plugin(placeholder, 'TextPlugin', SRC_LANG, body=body)
                self.stdout.write('Homepage: conteudo EN substituido por versao inglesa.')

            # --- 5. Publicar ambos ---
            for lang in (SRC_LANG, DST_LANG):
                try:
                    page.publish(lang)
                except Exception as exc:  # noqa: BLE001 - queremos continuar
                    self.stdout.write(self.style.WARNING(
                        'Falha a publicar %s em %s: %s' % (src.slug, lang, exc)
                    ))

        # --- 6. Static placeholders (rodape) ---
        # Estes sao partilhados entre paginas e tem conteudo por idioma. Nao
        # tem publish() sem request, por isso copiamos para o rascunho e para
        # a versao publica.
        for sp in StaticPlaceholder.objects.all():
            for placeholder in (sp.draft, sp.public):
                if not placeholder:
                    continue
                if placeholder.get_plugins_list(language=DST_LANG):
                    continue
                src_plugins = placeholder.get_plugins_list(language=SRC_LANG)
                if not src_plugins:
                    continue
                copy_plugins_to(src_plugins, placeholder, to_language=DST_LANG)
                copied += 1

        self.stdout.write(self.style.SUCCESS(
            'Concluido. Titulos PT criados: %d | titulos atualizados: %d | '
            'placeholders copiados: %d' % (created, updated, copied)
        ))
