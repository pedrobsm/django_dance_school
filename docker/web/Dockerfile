FROM python:3.10-slim-bullseye

# Debian Bullseye já não está nos espelhos normais — aponta o apt para o arquivo
RUN sed -i 's|deb.debian.org/debian|archive.debian.org/debian|g; s|security.debian.org/debian-security|archive.debian.org/debian-security|g' /etc/apt/sources.list && \
    echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99no-check-valid-until

# Initialize
RUN mkdir -p /data/web
WORKDIR /data/web
COPY ./requirements.txt /data/web/
COPY ./custom/requirements.txt /data/web/requirements_custom.txt
COPY manage.py /data/web

# Setup
RUN apt-get update
RUN apt-get -y upgrade
RUN apt-get -y install postgresql-client gettext gcc gettext zlib1g libjpeg-dev python3-cffi libffi-dev git musl-dev libpango-1.0-0 libpangocairo-1.0-0 python3-cairo-dev libjxr-tools libgdk-pixbuf2.0-dev shared-mime-info fonts-liberation2
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt
RUN pip3 install -r requirements_custom.txt

# Add custom apps to PYTHONPATH
ENV PYTHONPATH "$PYTHONPATH:/data/web/custom"

# Clean
RUN apt-get -y remove postgresql-client git
RUN apt -y autoremove

# Prepare
COPY ./school/ /data/web/school/
