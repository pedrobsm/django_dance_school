"""school URL Configuration — CMS 5 / Django 5.2

Reescrito a partir do original (CMS 3 / Django 3.1). A única mudança
estrutural é `django.conf.urls.url` -> `django.urls.re_path`: `url()` foi
descontinuado no Django 3.1 e **removido** no Django 4.0 — com Django 5.2
o import antigo (`from django.conf.urls import include, url`) nem sequer
carrega. `re_path()` aceita a mesma sintaxe de regex, por isso o resto do
ficheiro não precisou de mudar.

`django.conf.urls.static.static` e `django.conf.urls.i18n` continuam
válidos em Django 5.2 (não foram afetados pela remoção de `url()`).
"""
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, re_path
from django.views.generic import RedirectView

urlpatterns = [
    # O browser pede /favicon.ico na raiz por sua conta. Sem esta rota, o
    # pedido cai no i18n_patterns, ganha prefixo de idioma e acaba em
    # /en/favicon.ico/ -> 404 (era a maioria dos 404 nos logs).
    re_path(
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
    re_path(r'^i18n/', include('django.conf.urls.i18n')),
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
    re_path(r'^admin/', admin.site.urls),
    # Include your own app's URLs first to override default app URLs
    # re_path(r'^', include('your_app.urls')),
    # Now, include default app URLs
    re_path(r'^', include('danceschool.urls')),
    re_path(r'^', include('cms.urls')),
)
