"""
Default Django settings for the HOP IN Dance School project — CMS 5 / Django 5.2.

Reescrito de raiz para o `0.9.0-dev` do django-danceschool (Django 5.2,
django-cms 5.0.1, djangocms-frontend/Bootstrap 5, djangocms-versioning,
djangocms-alias). NÃO é uma migração incremental do settings.py antigo
(CMS 3/Django 3.1) — a doc oficial do 0.9.0-dev está desatualizada (ver
CLAUDE.md), por isso o INSTALLED_APPS abaixo foi montado a partir de:
1. install_requires do setup.py do django-danceschool 0.9.0-dev;
2. leitura direta do código de cada app (cms_apps.py, cms_plugins.py,
   forms/*.py) para confirmar os nomes reais dos pacotes CMS 5
   (ex: `djangocms_text`, não `djangocms_text_ckeditor`);
3. READMEs oficiais de cada pacote django-cms (versioning, alias,
   frontend, text) em vez da doc do django-danceschool.

Itens marcados "A CONFIRMAR" são o melhor palpite fundamentado a partir
dessa pesquisa, mas só ficam confirmados no primeiro `migrate`/arranque
real — corrigir aqui conforme os erros que aparecerem (mesmo padrão já
usado no CLAUDE.md para pins de versão).

Como sempre, nunca commitar credenciais reais (SECRET_KEY, password da
BD, etc.) — vêm todas de env vars / Docker secrets.
"""

import os
from os import environ
import dj_database_url
import dj_email_url
from logging.handlers import SysLogHandler


from huey import RedisHuey
from redis import ConnectionPool

# Importa um grande número de defaults (INSTALLED_APPS/MIDDLEWARE NÃO estão
# entre eles — ver nota no topo deste ficheiro, o pacote deixou de os
# definir a partir do 0.9.0-dev). Pode sempre ser sobreposto abaixo.
from danceschool.default_settings import *  # noqa: F401,F403


def boolify(s):
    ''' translate environment variables to booleans '''
    if isinstance(s, bool) or isinstance(s, int):
        return s
    s = s.strip().lower()
    return int(s) if s.isdigit() else s == 'true'


def get_secret(secret_name):
    ''' For Docker Swarms, the secret key and Postgres info are kept in secrets, not in the environment. '''
    try:
        with open('/run/secrets/{0}'.format(secret_name), 'r') as secret_file:
            return secret_file.read().rstrip('\n')
    except IOError:
        return None


# Required by Django CMS to determine default URLs for pages.
SITE_ID = 1

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = get_secret('django_secret_key') or environ.get('SECRET_KEY')

DEBUG = boolify(environ.get('DEBUG', False))

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver', environ.get('ALLOWED_HOST') or '']


# Application definition
#
# Ordem preservada do settings.py antigo onde possível (CMS/dynamic_preferences
# primeiro, apps custom antes do tema, tema antes do core, contrib do Django
# por último) — essa ordem importa para a descoberta de plugins/templates.

INSTALLED_APPS = [
    # O CMS vai primeiro para encontrar plugins nas outras apps instaladas.
    'cms',

    # A dynamic_preferences vai a seguir para encontrar/registar preferências
    # do projeto definidas noutras apps.
    'dynamic_preferences',

    # Apps custom da HOP IN.
    'democontent',
    # 'hopintheme' DESATIVADA de propósito por agora (2026-08-28) — os seus
    # templates (cms/home.html, etc.) são cópias do CMS3/Bootstrap4 com tags
    # removidas no CMS5 (`{% static_placeholder %}`, substituída por
    # `{% static_alias %}` no template stock do business_frontpage). Isso
    # rebentava silenciosamente o scan de placeholders do django-cms 5
    # (`get_declared_placeholders_for_obj` devolvia `[]` para `cms/home.html`
    # quando o override do hopintheme vencia por ordem de INSTALLED_APPS),
    # o que fazia o `setupschool` falhar com `Placeholder.DoesNotExist` ao
    # criar a Home page. Já estava identificado no plano da migração CMS5
    # como trabalho da Fase 4 ("templates Bootstrap4/CMS3, vai precisar de
    # reescrita") — reativar só depois de reescrever para CMS5/Bootstrap5,
    # não com um patch pontual. Ver CLAUDE.md.
    # 'hopintheme',

    # Tema base do projeto (plugins Bootstrap "clássicos" do próprio
    # danceschool, distintos do djangocms_frontend abaixo).
    'danceschool.themes.business_frontpage',
    'danceschool.themes',

    # App core do projeto — obrigatória.
    'danceschool.core',

    # Apps opcionais, ativas por omissão.
    'danceschool.financial',
    'danceschool.private_events',
    'danceschool.discounts',
    'danceschool.vouchers',
    'danceschool.prerequisites',
    'danceschool.stats',
    'danceschool.news',
    'danceschool.faq',
    'danceschool.banlist',
    'danceschool.guestlist',
    'danceschool.register',
    'danceschool.merch',
    # 'danceschool.backups',
    # 'danceschool.private_lessons',

    # Apps de pagamento são ativadas condicionalmente mais abaixo, exceto
    # "pay at door" que não precisa de tokens externos:
    # 'danceschool.payments.payatdoor',

    # Requeridas pelo django-cms.
    'menus',
    'sekizai',
    'treebeard',

    # Drag-and-drop na ordenação de conteúdo no admin.
    'adminsortable2',

    # Autenticação.
    'allauth',
    'allauth.account',
    'allauth.socialaccount',

    # Rich text do CMS 5 — substitui djangocms_text_ckeditor (CMS 3).
    # Confirmado no código de 0.9.0-dev: danceschool/core/forms/email.py
    # importa `djangocms_text.widgets.TextEditorWidget`, e
    # setup_permissions.py já lista 'djangocms_text' (não mais
    # '..._ckeditor'). Editor por omissão é o TipTap, incluído no pacote base.
    'djangocms_text',
    # Contrib opcional para inserir imagens do django-filer no editor — é o
    # equivalente ao antigo 'ckeditor_filebrowser_filer'.
    'djangocms_text.contrib.filer_image',

    # Seletor de cores (setup.py: django-colorful>=1.3).
    'colorful',

    # Forms bonitos, agora em Bootstrap 5 (confirmado no código:
    # danceschool/core/forms/email.py já usa classes/atributos `data-bs-*`).
    'crispy_forms',
    'crispy_bootstrap5',

    # Plugins CMS "clássicos" ainda usados diretamente pelo core do
    # danceschool — confirmado em danceschool/themes/cms_plugins.py, que
    # ainda deriva de djangocms_picture.cms_plugins.PicturePlugin para o
    # plugin de imagem de splash. djangocms_link é dependência obrigatória
    # do djangocms_frontend a partir da v2.
    'djangocms_icon',
    'djangocms_link',
    'djangocms_picture',

    # django CMS Frontend — substitui djangocms_bootstrap4 (Bootstrap 5).
    # Lista de contrib apps escolhida para dar paridade com os componentes
    # Bootstrap 4 que já usávamos (alerts/badge/card/carousel/collapse/
    # content/grid/jumbotron/link/listgroup/media/tabs/utilities). 'image'
    # é o componente de imagem novo da frontend (distinto de djangocms_picture
    # acima, que o core do danceschool usa por si só para o splash).
    'easy_thumbnails',
    'djangocms_frontend',
    'djangocms_frontend.contrib.accordion',
    'djangocms_frontend.contrib.alert',
    'djangocms_frontend.contrib.badge',
    'djangocms_frontend.contrib.card',
    'djangocms_frontend.contrib.carousel',
    'djangocms_frontend.contrib.collapse',
    'djangocms_frontend.contrib.content',
    'djangocms_frontend.contrib.grid',
    'djangocms_frontend.contrib.image',
    'djangocms_frontend.contrib.jumbotron',
    'djangocms_frontend.contrib.link',
    'djangocms_frontend.contrib.listgroup',
    'djangocms_frontend.contrib.media',
    'djangocms_frontend.contrib.tabs',
    'djangocms_frontend.contrib.utilities',

    # Versionamento de conteúdo (substitui o modelo draft/published do CMS 3)
    # e Aliases (substitui os static placeholders do CMS 3, ex. rodapé).
    'djangocms_versioning',
    'djangocms_alias',
    'parler',  # dependência obrigatória do djangocms_alias

    # Autocomplete (usado em danceschool/core/forms/email.py, entre outros)
    # — vai antes do admin, tal como no settings.py antigo.
    'dal',
    'dal_select2',
    'django_addanother',

    # Filtro por múltiplos emails num único campo (EmailContactForm).
    'multi_email_field',

    # Filtros de data/lista no admin. O setup.py do 0.9.0-dev troca o antigo
    # 'django-admin-rangefilter<0.7' (pin fóssil, ver CLAUDE.md) por
    # 'django-admin-rangefilter>=0.13.2' (sem upper pin — o bug de
    # compatibilidade que motivou o pin já não se aplica) e ACRESCENTA
    # 'django-admin-list-filter-dropdown>=1.0.3'. A CONFIRMAR: o nome exato
    # da app deste segundo pacote no INSTALLED_APPS
    # (`django_admin_listfilter_dropdown`, conforme a doc do PyPI) só é
    # validado no primeiro arranque — se o Django reclamar de app não
    # encontrada, corrigir aqui.
    'rangefilter',
    'django_admin_listfilter_dropdown',

    # Admin mais bonito para o CMS.
    'djangocms_admin_style',

    # Export de views para PDF.
    'easy_pdf',

    # Gestão de ficheiros/imagens.
    'filer',

    # Agendamento de tarefas.
    'huey.contrib.djhuey',

    # Multi-table inheritance para Event.
    'polymorphic',

    # Amazon S3 ou outro backend de storage, se configurado abaixo.
    'storages',

    # Substitui o handling de staticfiles do Django pelo WhiteNoise, para
    # consistência entre gunicorn e `./manage.py runserver`.
    'whitenoise.runserver_nostatic',

    # Apps do Django e suas dependências.
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.sitemaps',
    'django.contrib.admin',
]

MIDDLEWARE = [
    # Necessário pelo django-cms para recarregar apphooks de forma
    # inteligente quando mudam (ver danceschool/core/cms_apps.py —
    # RegistrationApphook).
    'cms.middleware.utils.ApphookReloadMiddleware',
    # Usado pelo WhiteNoise para servir estáticos.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    # Middlewares exigidos pelo django-cms.
    'cms.middleware.user.CurrentUserMiddleware',
    'cms.middleware.page.CurrentPageMiddleware',
    'cms.middleware.toolbar.ToolbarMiddleware',
    'cms.middleware.language.LanguageCookieMiddleware',
    # Exigido pelo django-allauth a partir de uma versão bem mais recente do
    # que a que corria com Django 3.1/CMS3 (setup.py do 0.9.0-dev pede
    # django-allauth>=65.9.0) — sem isto, allauth.account.apps.AccountConfig
    # .ready() recusa-se a arrancar com ImproperlyConfigured. Descoberto ao
    # correr `manage.py check` pela primeira vez nesta VM (2026-08-28).
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'school.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.static',
                'django.template.context_processors.csrf',
                'sekizai.context_processors.sekizai',
                'cms.context_processors.cms_settings',
                'danceschool.core.context_processors.site',
            ],
            'debug': False,
        },
    }
]

WSGI_APPLICATION = 'school.wsgi.application'


# Database

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

DB_URL = get_secret('postgres_url') or environ.get('DATABASE_URL')
DATABASES['default'].update(dj_database_url.config(default=DB_URL, conn_max_age=500))

# Django 5.x recomenda BigAutoField por omissão (DEFAULT_AUTO_FIELD já vem
# definido como AutoField em danceschool.default_settings — mantido por
# consistência com as migrações existentes do pacote, não mudar sem correr
# `makemigrations` para todas as apps).

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'formatters': {
        'verbose': {
            'format': '[contactor] %(levelname)s %(asctime)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': environ.get('LOGGING_LEVEL', 'DEBUG'),
            'class': 'logging.StreamHandler',
        },
        'syslog': {
            'level': 'INFO',
            'class': 'logging.handlers.SysLogHandler',
            'facility': SysLogHandler.LOG_LOCAL2,
            'address': '/dev/log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'boto': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        }
    }
}

# Internacionalização — HOP IN comunica sobretudo em português europeu (ver
# CLAUDE.md), com inglês como segunda língua.
LANGUAGE_CODE = environ.get('LANGUAGE_CODE', 'pt')

# Sobrepõe o LANGUAGES = [('en', 'English')] herdado de
# danceschool.default_settings (importado com `*` no topo deste ficheiro).
LANGUAGES = [
    ('pt', 'Português'),
    ('en', 'English'),
]

# LOCALE_PATHS tem prioridade sobre os catálogos das apps instaladas — traduz
# o pacote django-danceschool sem editar site-packages.
LOCALE_PATHS = [os.path.join(BASE_DIR, 'locale')]

CMS_LANGUAGES = {
    SITE_ID: [
        {
            'code': 'pt',
            'name': 'Português',
            'public': True,
            'hide_untranslated': False,
            'redirect_on_fallback': False,
            'fallbacks': ['en'],
        },
        {
            'code': 'en',
            'name': 'English',
            'public': True,
            'hide_untranslated': False,
            'redirect_on_fallback': False,
            'fallbacks': ['pt'],
        },
    ],
    'default': {
        'public': True,
        'hide_untranslated': False,
        'redirect_on_fallback': False,
        'fallbacks': ['pt', 'en'],
    },
}

TIME_ZONE = environ.get('TIME_ZONE', 'Europe/Lisbon')

USE_I18N = True
USE_L10N = True
USE_TZ = True

# Huey (Redis)
pool = ConnectionPool.from_url(environ.get('REDIS_URL'))
HUEY = RedisHuey('danceschool', connection_pool=pool)

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(PROJECT_ROOT, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Requerido pelo django-cms para que as frames do admin carreguem.
X_FRAME_OPTIONS = 'SAMEORIGIN'

# django CMS 5 — flag de compatibilidade nova (não existia no CMS 3/4). A
# CONFIRMAR o que exatamente ativa: aparece em danceschool.default_settings
# do 0.9.0-dev sem comentário explicativo; manter True (o valor upstream) até
# se perceber melhor o efeito, e documentar aqui assim que soubermos.
CMS_CONFIRM_VERSION4 = True

# AWS, se configurado no ambiente; caso contrário, storage local.
if (
    'AWS_STORAGE_BUCKET_NAME' in environ and
    'AWS_SECRET_ACCESS_KEY' in environ and
    'AWS_STORAGE_BUCKET_NAME' in environ
):
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    AWS_ACCESS_KEY_ID = environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = environ.get('AWS_STORAGE_BUCKET_NAME')
else:
    MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'media')
    MEDIA_URL = '/media/'

# Processadores de pagamento — ativados condicionalmente conforme as
# variáveis de ambiente disponíveis.
PAYPAL_MODE = environ.get('PAYPAL_MODE', 'sandbox')
PAYPAL_CLIENT_ID = environ.get('PAYPAL_CLIENT_ID')
PAYPAL_CLIENT_SECRET = environ.get('PAYPAL_CLIENT_SECRET')

if PAYPAL_MODE and PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET:
    INSTALLED_APPS.append('danceschool.payments.paypal')

SQUARE_LOCATION_ID = environ.get('SQUARE_LOCATION_ID')
SQUARE_APPLICATION_ID = environ.get('SQUARE_APPLICATION_ID')
SQUARE_ACCESS_TOKEN = environ.get('SQUARE_ACCESS_TOKEN')

if SQUARE_LOCATION_ID and SQUARE_ACCESS_TOKEN and SQUARE_APPLICATION_ID:
    INSTALLED_APPS.append('danceschool.payments.square')

STRIPE_PUBLIC_KEY = environ.get('STRIPE_PUBLIC_KEY')
STRIPE_PRIVATE_KEY = environ.get('STRIPE_PRIVATE_KEY')

if STRIPE_PUBLIC_KEY and STRIPE_PRIVATE_KEY:
    INSTALLED_APPS.append('danceschool.payments.stripe')

# Email via $EMAIL_URL (definido em env.default). Sendgrid e Gmail usam SMTP.
if 'EMAIL_URL' in environ:
    email_config = dj_email_url.config()
    EMAIL_FILE_PATH = email_config.get('EMAIL_FILE_PATH')
    EMAIL_HOST_USER = email_config.get('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = email_config.get('EMAIL_HOST_PASSWORD')
    EMAIL_HOST = email_config.get('EMAIL_HOST')
    EMAIL_PORT = email_config.get('EMAIL_PORT')
    EMAIL_BACKEND = email_config.get('EMAIL_BACKEND')
    EMAIL_USE_TLS = email_config.get('EMAIL_USE_TLS')
    EMAIL_USE_SSL = email_config.get('EMAIL_USE_SSL')

DEFAULT_FROM_EMAIL = environ.get('DEFAULT_FROM_EMAIL', 'webmaster@localhost')
SERVER_EMAIL = environ.get('SERVER_EMAIL', DEFAULT_FROM_EMAIL)

# Crispy forms — Bootstrap 5 (setup.py: crispy-bootstrap5). O
# CRISPY_TEMPLATE_PACK também já vem definido como 'bootstrap5' em
# danceschool.default_settings; repetido aqui por clareza.
CRISPY_ALLOWED_TEMPLATE_PACKS = ('bootstrap5',)
CRISPY_TEMPLATE_PACK = 'bootstrap5'
CRISPY_FAIL_SILENTLY = True

# Cache/sessões via Redis.
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": environ.get('REDIS_URL'),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

BACKUP_LOCATION = environ.get('BACKUP_LOCATION', '/backup')

# Nightly backups (ativar via env var)
BACKUP_NIGHTLY_ENABLED = environ.get('BACKUP_NIGHTLY_ENABLED', False)

# Mailchimp
MAILCHIMP_API_KEY = environ.get('MAILCHIMP_API_KEY', '')
MAILCHIMP_LIST_ID = environ.get('MAILCHIMP_LIST_ID', '')
