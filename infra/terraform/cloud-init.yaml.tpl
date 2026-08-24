#cloud-config
package_update: true
package_upgrade: true
timezone: Europe/Lisbon

packages:
  - docker.io
  - git
  - ufw
  - fail2ban
  - parted

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
      - Log do bootstrap deste cloud-init: /var/log/hopin-bootstrap.log

  - path: /opt/hopin/bootstrap.sh
    owner: root:root
    permissions: "0755"
    content: |
      #!/bin/bash
      # Corre uma única vez via runcmd. Todo o shell script vive aqui (em vez
      # de dentro do runcmd: da cloud-config) para evitar problemas de
      # parsing YAML com aspas/dois-pontos/pipes dentro de comandos.
      set -euo pipefail

      systemctl enable --now docker
      usermod -aG docker ${admin_username}

      # Plugin docker compose v2 — best-effort, não aborta o resto se faltar
      # no repositório (docker stack deploy, que é o fluxo usado por este
      # projeto, não precisa dele).
      apt-get install -y docker-compose-v2 || echo "AVISO: docker-compose-v2 nao instalado, ver INFRA_NOTES.md"

      # Swap (a VM pode ter só 4GB de RAM a correr Postgres+Redis+Django+Huey+Nginx)
      if [ ! -f /swapfile ]; then
        fallocate -l 2G /swapfile
        chmod 600 /swapfile
        mkswap /swapfile
        swapon /swapfile
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
      fi

      # Firewall
      ufw allow OpenSSH
      ufw allow 80/tcp
      ufw allow 443/tcp
      ufw --force enable

      # fail2ban com defaults (protege o SSH exposto)
      systemctl enable --now fail2ban

      # Disco de dados: é anexado à VM como recurso Terraform separado,
      # DEPOIS da VM já existir — por isso pode não estar presente ainda no
      # primeiro boot. Espera até 60s pelo dispositivo antes de desistir.
      DEV=/dev/disk/azure/scsi1/lun0
      for i in $(seq 1 30); do
        [ -e "$DEV" ] && break
        sleep 2
      done

      if [ -e "$DEV" ] && [ ! -e "$DEV-part1" ]; then
        parted -s "$DEV" mklabel gpt
        parted -s "$DEV" mkpart primary ext4 0% 100%
        udevadm settle
        sleep 2
        mkfs.ext4 -F "$DEV-part1"
      fi

      if [ -e "$DEV-part1" ]; then
        grep -q "$DEV-part1" /etc/fstab || echo "$DEV-part1 /data ext4 defaults,nofail 0 2" >> /etc/fstab
        mkdir -p /data
        mount -a
        mkdir -p /data/docker-volumes
      else
        echo "AVISO: disco de dados nao apareceu a tempo, /data nao montado. Ver INFRA_NOTES.md" >&2
      fi

      # Código da aplicação
      mkdir -p /opt/hopin
      if [ ! -d /opt/hopin/app/.git ]; then
        git clone ${github_repo_url} /opt/hopin/app
      fi

      chown -R ${admin_username}:${admin_username} /opt/hopin /data

      %{ if ghcr_username != "" && ghcr_token != "" ~}
      echo "${ghcr_token}" | docker login ghcr.io -u "${ghcr_username}" --password-stdin
      %{ endif ~}

      echo "cloud-init concluido" > /opt/hopin/.provisioned

runcmd:
  - bash /opt/hopin/bootstrap.sh 2>&1 | tee /var/log/hopin-bootstrap.log
