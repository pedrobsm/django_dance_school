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
    url = translate_url(current, lang_code)

    if url == current:
        # translate_url so troca o URL se conseguir resolve-lo e voltar a
        # gera-lo no idioma de destino. Quando nao consegue (vistas fora do
        # URLconf traduzivel), trocamos o prefixo a mao para o link nao
        # ficar a apontar ao mesmo idioma.
        codes = dict(settings.LANGUAGES)
        parts = current.split('/', 2)
        if len(parts) > 2 and parts[1] in codes:
            url = '/{0}/{1}'.format(lang_code, parts[2])

    return url
