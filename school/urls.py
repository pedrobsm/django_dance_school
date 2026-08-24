"""school URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.views.generic import RedirectView

urlpatterns = [
    # O browser pede /favicon.ico na raiz por sua conta. Sem esta rota, o
    # pedido cai no i18n_patterns, ganha prefixo de idioma e acaba em
    # /en/favicon.ico/ -> 404 (era a maioria dos 404 nos logs).
    url(
        r'^favicon\.ico$',
        RedirectView.as_view(
            url='{0}images/favicon.ico'.format(settings.STATIC_URL),
            permanent=True,
        ),
    ),

    # Vistas de i18n do Django (set_language). O seletor de idioma do navbar
    # não a usa — troca de idioma por link GET, porque o django-cms serve
    # páginas a partir da cache e um POST com CSRF rebentava com 403
    # intermitente (ver custom/hopintheme/templatetags/hopin_i18n.py). Fica
    # disponível na mesma, e de propósito FORA de i18n_patterns: é a vista
    # que *muda* de idioma, não pode estar presa a um.
    url(r'^i18n/', include('django.conf.urls.i18n')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Tudo passa a ter prefixo de idioma (/pt/..., /en/...), INCLUINDO o admin.
#
# O admin tem mesmo de estar aqui dentro: é o que o django-cms assume (o
# template oficial de projeto do django-cms põe o admin dentro do
# i18n_patterns) e a barra de ferramentas do CMS gera links de admin
# relativos à página atual. Com o admin fora daqui, esses links saíam como
# /en/admin/core/staffmember/ e davam 404 — confirmado nos logs do nginx.
#
# Efeito lateral positivo: o idioma do admin passa a vir do URL em vez do
# cookie, o que torna o comportamento previsível. /admin/ sem prefixo
# continua a funcionar — o LocaleMiddleware redireciona para /pt/admin/ ou
# /en/admin/ conforme o idioma ativo.
#
# Nota: isto também prefixa o sitemap.xml e as URLs do django-filer que
# vêm dentro de danceschool.urls. Não é ideal para o sitemap (o
# convencional seria /sitemap.xml sem prefixo), mas essas URLs são todas
# resolvidas por reverse() no código, por isso continuam a funcionar.
urlpatterns += i18n_patterns(
    url(r'^admin/', admin.site.urls),
    # Include your own app's URLs first to override default app URLs
    # url(r'^', include('your_app.urls')),
    # Now, include default app URLs
    url(r'^', include('danceschool.urls')),
    url(r'^', include('cms.urls')),
)
