# -*- coding: utf-8 -*-
"""Template tags de i18n especificas da HOP IN."""
from django import template
from django.conf import settings
from django.urls import translate_url

register = template.Library()


@register.simple_tag(takes_context=True)
def switch_language_url(context, lang_code):
    """
    Devolve o URL da pagina atual no idioma `lang_code`.

    Porque nao usamos a vista set_language do Django (POST): o django-cms
    tem cache de pagina ligada por omissao (CMS_PAGE_CACHE, Cache-Control:
    max-age=60). Uma pagina servida a partir da cache leva embutido o token
    CSRF de quem a renderizou primeiro e nao traz Set-Cookie, por isso o
    POST do utilizador rebenta com 403 de forma intermitente. Um link GET
    nao tem esse problema e e seguro em cache — o URL ja identifica o
    idioma, porque as rotas publicas estao dentro de i18n_patterns.
    """
    request = context.get('request')
    if request is None:
        return '/{0}/'.format(lang_code)

    current = request.get_full_path()

    # 1) translate_url resolve o URL atual e volta a gera-lo no idioma de
    #    destino. E a melhor opcao quando funciona, porque preserva URLs
    #    profundos (ex.: o detalhe de uma noticia dentro de um apphook).
    url = translate_url(current, lang_code)
    if url != current:
        return url

    # 2) Se nao mudou nada, nao conseguiu resolver. O caso tipico e uma
    #    pagina CMS simples: o translate_url reverte para cms.views.details
    #    com o *mesmo* slug, mas os slugs mudam de idioma para idioma
    #    (/en/calendar/ vs /pt/calendario/). A propria pagina sabe o seu URL
    #    em cada idioma, prefixo de idioma incluido.
    page = getattr(request, 'current_page', None)
    if page is not None:
        try:
            page_url = page.get_absolute_url(language=lang_code)
        except Exception:  # noqa: BLE001 - nunca rebentar o navbar por isto
            page_url = None
        if page_url:
            return page_url

    # 3) Ultimo recurso: trocar o prefixo a mao, para o link pelo menos nao
    #    ficar a apontar ao idioma em que ja estamos.
    codes = dict(settings.LANGUAGES)
    parts = current.split('/', 2)
    if len(parts) > 2 and parts[1] in codes:
        return '/{0}/{1}'.format(lang_code, parts[2])

    return url
