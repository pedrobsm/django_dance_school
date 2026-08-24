# Infraestrutura Azure — HOP IN (PoC)

Terraform para provisionar **uma única VM Ubuntu 22.04** no Azure com tudo o
necessário para correr a stack Docker/Swarm do `django-danceschool`
(web + huey + postgres + redis + nginx), mais acesso SSH pronto a usar.

Este PC não consegue fazer `az login` (restrições administrativas). Corre
tudo isto a partir de outro PC onde consigas autenticar-te no Azure.

## O que isto cria

- Resource Group, VNet/Subnet, NSG (só abre 22/80/443)
- IP público estático
- VM `Standard_B2s` (2 vCPU / 4GB, ~28€/mês) com disco de SO (32GB) e um
  disco de dados separado (32GB, montado em `/data`) para o Postgres,
  media/static files e backups
- Acesso SSH só por chave (password auth desligada), restrito ao(s) IP(s)
  que definires em `allowed_ssh_cidrs`
- Cloud-init que instala Docker, Docker Compose v2, `ufw`, `fail2ban`,
  configura swap, e clona o repositório para `/opt/hopin/app`

**O que isto NÃO faz automaticamente**: `docker swarm init`, criação de
secrets/volumes, build/pull das imagens, migrações, certificados TLS. Esse
fluxo (`docker/setup_stack.sh`) é interativo de propósito (pede confirmações,
gera credenciais) — corre-se manualmente depois de entrares por SSH. Ver
`/opt/hopin/INFRA_NOTES.md` na VM depois do provisionamento.

## Pré-requisitos no outro PC

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.7
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)
- Cliente OpenSSH (`ssh-keygen`, já vem com Windows 10/11, macOS, Linux)
- Acesso à subscrição Azure da HOP IN

## Passo a passo

### 1. Autenticar no Azure

```bash
az login
az account set --subscription "<nome-ou-id-da-subscrição>"
```

### 2. Gerar o par de chaves SSH dedicado a esta VM

A partir da pasta `infra/terraform`:

```bash
mkdir -p ssh
ssh-keygen -t ed25519 -f ./ssh/hopin_vm_key -C "hopin-vm" -N ""
```

Isto cria `ssh/hopin_vm_key` (privada — nunca commitar, já está no
`.gitignore`) e `ssh/hopin_vm_key.pub` (pública, é a que o Terraform lê).

### 3. Configurar variáveis

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edita `terraform.tfvars`:
- `allowed_ssh_cidrs`: o teu IP público atual em formato `/32`. Descobre com
  `curl ifconfig.me` (ou pesquisa "qual é o meu IP").
- `domain_name` / `acme_email`: preenche se já tiveres domínio decidido,
  senão deixa vazio e trata disso depois por SSH.

Se o package `ghcr.io/pedrobsm/danceschool-web` for privado, define também
(fora do ficheiro, por variável de ambiente, para não ficar em disco):

```bash
export TF_VAR_ghcr_username=pedrobsm
export TF_VAR_ghcr_token=ghp_xxxxx   # PAT com scope read:packages
```

### 4. Provisionar

```bash
terraform init
terraform plan
terraform apply
```

No final, o Terraform mostra o IP público e o comando SSH pronto a usar.

### 5. Confirmar acesso SSH

```bash
ssh -i ./ssh/hopin_vm_key hopinadmin@<public_ip_address>
cat /opt/hopin/INFRA_NOTES.md
```

Dá 1-2 minutos depois do `apply` para o cloud-init terminar antes de tentares
ligar. Para acompanhar o progresso já ligado por SSH:

```bash
cloud-init status --wait
```

### 6. Apontar o domínio

Cria um registo DNS **A** do teu domínio (ou subdomínio) para o
`public_ip_address` do output. Só depois disso o Let's Encrypt (via
`letsencrypt-nginx-proxy-companion` já presente no `docker-compose.yml`)
consegue emitir o certificado.

### 7. Arrancar a aplicação

Já dentro da VM por SSH, segue o fluxo existente do projeto (ver
`CLAUDE.md` no repo, secção "Estado da infraestrutura" e
`docker/setup_stack.sh`) para inicializar o swarm, criar secrets/volumes,
fazer `docker login ghcr.io` (se necessário), `docker pull`/`docker stack
deploy`, migrações e `createsuperuser`.

## Partilhar acesso com o Claude Code

Depois disto, para dares acesso SSH à VM numa sessão futura, precisas de:
- IP público da VM (`terraform output public_ip_address`)
- Chave privada `ssh/hopin_vm_key` (ou o caminho onde a guardaste)
- Utilizador `hopinadmin` (ou o que tiveres definido em `admin_username`)

## Atualizar o IP autorizado para SSH

Se mudares de rede/IP:

```bash
# edita allowed_ssh_cidrs em terraform.tfvars com o novo IP
terraform apply
```

## Custo estimado (West Europe, PoC)

| Recurso | Estimativa mensal |
|---|---|
| VM Standard_B2s | ~28€ |
| Disco SO (32GB StandardSSD) | ~2€ |
| Disco dados (32GB StandardSSD) | ~2€ |
| IP público Standard | ~3€ |
| Tráfego (baixo volume PoC) | ~1-3€ |
| **Total** | **~35-40€/mês** |

Dentro do limite de 80€/mês. Sobra margem para subir para
`Standard_B2ms` (4 vCPU/8GB, ~60€/mês) se a stack completa (Postgres + Redis
+ Django + Huey + Nginx) sentir falta de RAM.

## Destruir tudo

```bash
terraform destroy
```

Isto apaga a VM, discos (incluindo o disco de dados com a base de dados!) e
rede. Faz backup do Postgres antes, se houver dados que importem.
