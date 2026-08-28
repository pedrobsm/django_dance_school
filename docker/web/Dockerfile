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
