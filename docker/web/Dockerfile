FROM python:3.12-slim-bookworm

# Initialize
RUN mkdir -p /data/web
WORKDIR /data/web
COPY ./requirements.txt /data/web/
COPY ./custom/requirements.txt /data/web/requirements_custom.txt
COPY manage.py /data/web

# Setup. curl e patch são só precisos durante o build (para aplicar o PR
# #187 abaixo) e removidos a seguir, tal como o postgresql-client e o git.
RUN apt-get update
RUN apt-get -y upgrade
RUN apt-get -y install postgresql-client gettext gcc zlib1g libjpeg-dev python3-cffi libffi-dev git musl-dev libpango-1.0-0 libpangocairo-1.0-0 python3-cairo-dev libjxr-tools libgdk-pixbuf2.0-dev shared-mime-info fonts-liberation2 curl patch
RUN pip3 install --upgrade pip

# django-danceschool instalado a partir do Git, branch 0.9.0-dev — a versão
# no PyPI (0.9.3) é a fóssil CMS3/Django 3.1 (ver CLAUDE.md). NÃO trocar por
# `pip install django-danceschool` nem por um pin de versão do PyPI.
RUN pip3 install "git+https://github.com/django-danceschool/django-danceschool.git@0.9.0-dev"

# Patch obrigatório: setupschool (e os 4 setup_<processor>.py que invoca)
# está partido no 0.9.0-dev pelas mudanças de API do CMS 5 — release
# blocker upstream, corrigido no PR #187, ainda por fundir em 2026-08-28.
# Aplicado aqui diretamente sobre o site-packages instalado, a partir do
# commit exato (não do branch do PR, que pode ser reescrito sem aviso —
# ver CLAUDE.md). Se este `patch` falhar num build futuro, é sinal de que
# a base 0.9.0-dev avançou o suficiente para o PR já não aplicar sem
# conflitos — confirmar o estado do PR #187 antes de tentar contornar.
RUN SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])") \
    && curl -sL -o /tmp/pr187.patch https://github.com/django-danceschool/django-danceschool/commit/9ce23c9f0c77d203e64202e089d2e24dae801246.patch \
    && patch -p1 -d "$SITE_PACKAGES" < /tmp/pr187.patch \
    && rm /tmp/pr187.patch

# Patch local (nosso, não do PR #187): migrate_static_placeholders.py importa
# `StaticPlaceholder` de cms.models incondicionalmente, mas essa classe foi
# removida no CMS 5 — rebenta o import do módulo inteiro mesmo numa instalação
# nova, mesmo sem nenhum StaticPlaceholder para migrar. setupschool.py precisa
# de 3 helpers deste ficheiro (para criar os Aliases de footer/stats), que
# nunca tocam em StaticPlaceholder — só as funções de migração de facto (que
# não fazem sentido correr numa instalação CMS5 de raiz) é que usam. Ver
# CLAUDE.md, secção "Migração para CMS 5", para o contexto completo.
COPY docker/web/patches/0001-migrate_static_placeholders-cms5-import.patch /tmp/local0001.patch
RUN SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])") \
    && TARGET="$SITE_PACKAGES/danceschool/core/management/commands/migrate_static_placeholders.py" \
    # Este ficheiro vem do upstream com terminadores CRLF (só este, não os
    # outros que o PR #187 toca) — normaliza para LF antes de aplicar o
    # patch (em LF), senão o `patch` recusa por "different line endings".
    && sed -i 's/\r$//' "$TARGET" \
    && patch -p1 -d "$SITE_PACKAGES" < /tmp/local0001.patch \
    && rm /tmp/local0001.patch

# Patch local #2 (nosso, não do PR #187): create_versioned_page() (o wrapper
# que o PR #187 introduz em setupschool.py para create_page()+Version) chama
# `create_page(language=language, **create_page_kwargs)` sem `created_by`.
# O próprio django-cms 5 avisa quando isto acontece ("No user has been
# supplied... No version could be created") e, pior do que o aviso diz,
# também não popula os placeholders da página a partir do template nesse
# caso — get_page_placeholder() (também do PR #187) falha a seguir com
# Placeholder.DoesNotExist. Fix: passar created_by=user ao create_page(),
# como o próprio aviso do CMS sugere. Confirmado ao correr `setupschool` na
# vm-hopin-cms5poc em 2026-08-28 — ver CLAUDE.md.
RUN SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])") \
    && TARGET="$SITE_PACKAGES/danceschool/core/management/commands/setupschool.py" \
    && grep -q 'page = create_page(language=language, \*\*create_page_kwargs)' "$TARGET" \
    && sed -i 's/page = create_page(language=language, \*\*create_page_kwargs)/page = create_page(language=language, created_by=user, **create_page_kwargs)/' "$TARGET"

# Patch local #3 (nosso, não do PR #187): a Version criada por
# create_versioned_page() ficava sempre em draft — ver
# docker/web/patches/fix_publish_version.py para o diagnóstico completo
# (o manager do PageContent já cria uma Version DRAFT sozinho, por isso o
# get_or_create() do PR #187 nunca aplica o state=PUBLISHED pretendido).
# Confirmado na vm-hopin-cms5poc em 2026-08-28: todas as páginas ficavam
# invisíveis para visitantes anónimos, `/pt/` redirecionava para
# /pt/admin/login/. Ver CLAUDE.md.
COPY docker/web/patches/fix_publish_version.py /tmp/fix_publish_version.py
RUN python3 /tmp/fix_publish_version.py && rm /tmp/fix_publish_version.py

RUN pip3 install -r requirements.txt
RUN pip3 install -r requirements_custom.txt

# Copy the custom apps folder into the image (needed since we build via CI,
# not via the bind-mount volume the official setup expects)
COPY ./custom/ /data/web/custom/

# Add custom apps to PYTHONPATH
ENV PYTHONPATH "$PYTHONPATH:/data/web/custom"

# Clean
RUN apt-get -y remove postgresql-client git curl patch
RUN apt -y autoremove

# Prepare
COPY ./school/ /data/web/school/

# Traduções do projeto (LOCALE_PATHS aponta para /data/web/locale). Os .mo
# são compilados aqui em vez de commitados, por isso o .po é a única fonte
# de verdade no repositório. Usamos msgfmt diretamente e não
# `manage.py compilemessages` porque este último carrega o settings.py
# completo, que precisa de DATABASE_URL/SECRET_KEY — coisas que não existem
# durante o build da imagem.
COPY ./locale/ /data/web/locale/
RUN find /data/web/locale -name '*.po' -execdir msgfmt -o django.mo {} \;
