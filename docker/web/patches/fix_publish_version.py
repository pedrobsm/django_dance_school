"""
Patch local #3 (nosso, não do PR #187) aplicado no build da imagem Docker,
sobre o site-packages instalado (ver Dockerfile).

create_versioned_page() (helper que o PR #187 acrescenta a setupschool.py)
tenta marcar a página como publicada com:

    Version.objects.get_or_create(..., defaults={'state': PUBLISHED, ...})

Mas o manager do PageContent do djangocms_versioning já cria sozinho, como
efeito secundário do próprio .create() chamado por cms.api.create_page(),
uma Version em estado DRAFT. Como é get_or_create(), encontra essa Version
já existente e devolve-a tal e qual — os `defaults=` só se aplicam quando a
linha é mesmo criada de novo, o que aqui já não acontece. Resultado: todas
as páginas ficavam permanentemente em draft, invisíveis para visitantes
anónimos (confirmado na vm-hopin-cms5poc em 2026-08-28: `/pt/` redirecionava
para `/pt/admin/login/?next=/pt/admin/cms/pagecontent/`, o comportamento do
django-cms quando não há nenhuma página publicada para mostrar).

A correção certa não é outro get_or_create — é o método próprio da máquina
de estados do djangocms_versioning, `Version.publish(user)`, que muda o
estado e também despublica versões anteriores. Ver CLAUDE.md, secção
"Migração para CMS 5", para o contexto completo desta cadeia de patches.
"""
import site

SITE_PACKAGES = site.getsitepackages()[0]
TARGET = f"{SITE_PACKAGES}/danceschool/core/management/commands/setupschool.py"

OLD = """        Version.objects.get_or_create(
            content_type=content_ct,
            object_id=page_content.pk,
            defaults={'state': PUBLISHED if publish else DRAFT, 'created_by': user},
        )
        return page"""

NEW = """        version, _ = Version.objects.get_or_create(
            content_type=content_ct,
            object_id=page_content.pk,
            defaults={'state': PUBLISHED if publish else DRAFT, 'created_by': user},
        )
        # See docker/web/patches/fix_publish_version.py in the HOP IN repo for
        # why this explicit publish() call is needed on top of the
        # get_or_create() above.
        if publish and version.state != PUBLISHED:
            version.publish(user)
        return page"""

with open(TARGET, encoding='utf-8') as f:
    content = f.read()

if OLD not in content:
    raise SystemExit(
        'fix_publish_version.py: expected snippet not found in %s — '
        'upstream setupschool.py (PR #187) probably changed, re-check '
        'before building.' % TARGET
    )

with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(content.replace(OLD, NEW))

print('fix_publish_version.py: patched', TARGET)
