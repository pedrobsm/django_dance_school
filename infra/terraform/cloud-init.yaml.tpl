#cloud-config
package_update: true
package_upgrade: true
timezone: Europe/Lisbon

packages:
  - docker.io
  - git
  - ufw
  - fail2ban

# Disco de dados anexado como LUN 0 -> particiona, formata e monta em /data.
disk_setup:
  /dev/disk/azure/scsi1/lun0:
    table_type: gpt
    layout: true
    overwrite: false

fs_setup:
  - label: hopin_data
    filesystem: ext4
    device: /dev/disk/azure/scsi1/lun0
    partition: auto

mounts:
  - [/dev/disk/azure/scsi1/lun0-part1, /data, ext4, "defaults,nofail", "0", "2"]

write_files:
  - path: /opt/hopin/INFRA_NOTES.md
    owner: root:root
    permissions: "0644"
    content: |
      # Notas de infraestrutura (geradas pelo Terraform)

      - Repositório clonado em: /opt/hopin/app
      - Disco de dados persistente montado em: /data
        (usa /data/docker-volumes ou similar como bind mount para os volumes
        do docker-compose.yml — postgres, staticfiles, media, private_media,
        certs — em vez de volumes Docker anónimos, para facilitar backup.)
      - Imagem da app publicada por CI: ${ghcr_image}
      - Domínio alvo (VIRTUAL_HOST / LETSENCRYPT_HOST em env.web): ${domain_name}
        (hostname sslip.io automático se não foi dado domain_name — resolve
        para este IP sem DNS nenhum configurado; troca por domínio real
        mais tarde se necessário)
      - Email para Let's Encrypt (LETSENCRYPT_EMAIL em env.web): ${acme_email}
      - Recomendação: testa primeiro com LETSENCRYPT_TEST=true em env.web
        (certificado de staging, não fica válido no browser mas não gasta
        quota real) para confirmar que o challenge HTTP-01 chega até à VM
        antes de pedires o certificado de produção definitivo.
      - Firewall: ufw ativo, portas 22 (restrita), 80, 443 abertas.
      - Ver /opt/hopin/app/CLAUDE.md e /opt/hopin/app/docker/setup_stack.sh
        para o fluxo de arranque do stack (docker swarm init, secrets,
        volumes, certificados, migrações). Esse script é interativo —
        corre-o manualmente por SSH, não foi automatizado aqui de propósito.

runcmd:
  - systemctl enable --now docker
  - usermod -aG docker ${admin_username}

  # Plugin docker compose v2 (não faz parte do módulo "packages" acima para
  # não travar o resto do provisionamento se este pacote específico faltar
  # no repositório; nesse caso, instala manualmente por SSH depois).
  - apt-get install -y docker-compose-v2 || echo "AVISO: docker-compose-v2 não instalado automaticamente, ver /opt/hopin/INFRA_NOTES.md"

  # Swap (a VM pode ter só 4GB de RAM a correr Postgres+Redis+Django+Huey+Nginx)
  - fallocate -l 2G /swapfile
  - chmod 600 /swapfile
  - mkswap /swapfile
  - swapon /swapfile
  - echo '/swapfile none swap sw 0 0' >> /etc/fstab

  # Firewall
  - ufw allow OpenSSH
  - ufw allow 80/tcp
  - ufw allow 443/tcp
  - ufw --force enable

  # fail2ban com defaults (protege o SSH exposto)
  - systemctl enable --now fail2ban

  # Código da aplicação
  - mkdir -p /opt/hopin
  - test -d /opt/hopin/app/.git || git clone ${github_repo_url} /opt/hopin/app
  - mkdir -p /data/docker-volumes
  - chown -R ${admin_username}:${admin_username} /opt/hopin /data

  %{ if ghcr_username != "" && ghcr_token != "" ~}
  - echo "${ghcr_token}" | docker login ghcr.io -u "${ghcr_username}" --password-stdin
  %{ endif ~}

  - echo "cloud-init concluído" > /opt/hopin/.provisioned
