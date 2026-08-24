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
- `domain_name`: deixa vazio para a PoC. O Terraform usa automaticamente um
  hostname `sslip.io` derivado do IP público (ex: `20-50-60-70.sslip.io`) —
  ver caixa "Sobre o domínio/HTTPS" abaixo.
- `acme_email`: **obrigatório** mesmo sem domínio próprio — o Let's Encrypt
  exige um email de contacto para emitir certificados.

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

### 6. Domínio / HTTPS

Se deixaste `domain_name` vazio, o output `site_domain` já é um hostname
funcional (`terraform output site_domain`) — não precisas de fazer nada em
DNS, o `letsencrypt-nginx-proxy-companion` (já no `docker-compose.yml`)
consegue emitir o certificado diretamente contra esse hostname.

Se preenchesses `domain_name` com um domínio teu, cria antes um registo DNS
**A** a apontar para `public_ip_address`.

> **Sobre o domínio/HTTPS na PoC**: HTTPS em si não é opcional — sem ele,
> browsers em mobile bloqueiam acesso à câmara (upload de fotos) e cookies
> seguros, o que a PoC precisa. Mas não precisas de comprar um domínio: o
> `sslip.io` resolve automaticamente `<ip-com-hifens>.sslip.io` para o IP da
> VM, e o Let's Encrypt emite certificados válidos normais para ele. A única
> ressalva honesta: o `sslip.io` não está na Public Suffix List, por isso
> todos os utilizadores do serviço no mundo partilham a mesma quota do Let's
> Encrypt (elevada — 50 000 certificados/semana — mas não garantida, já
> houve episódios de esgotamento por tráfego de bots). Para uma VM só, o
> risco é baixo. Testa primeiro com `LETSENCRYPT_TEST=true` em `env.web`
> (emite um certificado de staging, não gasta a quota real) antes de pedir o
> certificado de produção definitivo.

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

## Problemas conhecidos (já corrigidos, mas fica registado)

**cloud-init falhou no primeiro `apply`** (VM `vm-hopin-poc`, 2026-08-24):
duas causas, já corrigidas em `cloud-init.yaml.tpl`, mas se voltares a ver
sintomas parecidos numa VM nova, o diagnóstico é este:

1. Uma linha do `runcmd:` continha `"AVISO: texto"` sem estar dentro de um
   bloco literal — o YAML interpretou o `:` como separador de mapa e partiu
   o `runcmd` inteiro (nenhum comando corria, incluindo `ufw`, `fail2ban`,
   swap, `docker` group). **Fix**: todo o shell script passou para
   `write_files` (`/opt/hopin/bootstrap.sh`, dentro de um bloco `content: |`
   literal, imune a este tipo de problema de parsing) e o `runcmd:` só
   invoca esse script.
2. O disco de dados é anexado à VM como recurso Terraform separado, depois
   da VM já existir — no primeiro boot, quando o `disk_setup`/`mounts` do
   cloud-init corria, o disco podia ainda não estar presente. **Fix**: o
   `bootstrap.sh` agora espera ativamente (até 60s) pelo dispositivo antes
   de particionar/formatar/montar, em vez de depender dos módulos
   declarativos do cloud-init (que só correm uma vez e falham
   permanentemente se o disco não estiver lá a tempo).

Confirma que o cloud-init terminou bem numa VM nova com:

```bash
ssh -i ./ssh/hopin_vm_key <user>@<ip> "cloud-init status --wait && cat /var/log/hopin-bootstrap.log"
```

**⚠️ Não corras `terraform apply`/`plan` na VM `vm-hopin-poc` já existente
sem cuidado**: a correção acima mudou o `custom_data` da VM, e o Azure só
aplica `custom_data` na criação — por isso o Terraform vai querer
**recriar a VM** (destruir e criar de novo) para "aplicar" essa alteração,
o que apagaria a app já instalada. Como a VM atual já foi corrigida
manualmente por SSH (swap, disco `/data`, `ufw`, `fail2ban` todos ativos),
**não precisas de reaplicar nada nela** — o `cloud-init.yaml.tpl` corrigido
só interessa para a *próxima* VM que criares de raiz (ex: depois de um
`terraform destroy`, ou um ambiente novo). Se correres `terraform plan` e
vires "must be replaced" por causa do `custom_data`, não avances com
`apply` sem teres a certeza de que queres mesmo recriar a VM.
