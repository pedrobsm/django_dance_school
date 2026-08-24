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

    # 1) Se estamos exatamente numa pagina CMS, e a pagina que sabe o seu
    #    proprio URL em cada idioma — os slugs mudam de idioma para idioma
    #    (/en/calendar/ vs /pt/calendario/).
    #
    #    Isto tem de vir ANTES do translate_url: o translate_url resolve
    #    /en/calendar/ para cms.views.details(slug='calendar') e volta a
    #    reverter isso no prefixo pt, produzindo /pt/calendar/ — um URL
    #    diferente do atual (logo, aparentemente bem sucedido) mas com o
    #    slug errado. O django-cms ate o salva com um 302, mas o link fica
    #    incorreto e custa um redirect a mais.
    #
    #    So o fazemos quando o pedido e a propria pagina. Em URLs mais
    #    profundos servidos por um apphook (ex.: o detalhe de uma noticia),
    #    current_page e a pagina do apphook, e usar o URL dela mandaria o
    #    utilizador para o indice em vez do artigo — nesse caso o
    #    translate_url faz melhor trabalho.
    page = getattr(request, 'current_page', None)
    if page is not None:
        try:
            here = page.get_absolute_url()
            if here and request.path == here:
                target = page.get_absolute_url(language=lang_code)
                if target:
                    return target
        except Exception:  # noqa: BLE001 - nunca rebentar o navbar por isto
            pass

    # 2) Vistas normais (danceschool) e URLs profundos de apphooks.
    url = translate_url(current, lang_code)
    if url != current:
        return url

    # 3) Ultimo recurso: trocar o prefixo a mao, para o link pelo menos nao
    #    ficar a apontar ao idioma em que ja estamos.
    codes = dict(settings.LANGUAGES)
    parts = current.split('/', 2)
    if len(parts) > 2 and parts[1] in codes:
        return '/{0}/{1}'.format(lang_code, parts[2])

    return url
