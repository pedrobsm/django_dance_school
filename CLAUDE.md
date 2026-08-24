# HOP IN — django-danceschool — Contexto do Projeto

## O que é isto

A HOP IN é uma associação de dança Swing e Blues no Porto, Portugal. Este
repositório é um fork de `django-danceschool/production-template`, usado para
gerir inscrições em aulas (mensalidades) e eventos/festas (bilhética),
incluindo um fluxo com três papéis: administradores (criam aulas/eventos),
alunos/participantes (inscrevem-se), e voluntários (confirmam presenças e
pagamentos).

Este é atualmente um **PoC** para avaliar se esta plataforma serve a
associação — não é ainda produção real. Comunicação sobre a HOP IN é bilingue, com prevalência de
**português europeu** mas sem descurar nunca o **inglês**.

- Fork: `github.com/pedrobsm/django_dance_school`
- Upstream original: `github.com/django-danceschool/production-template`
- Documentação do projeto: `django-danceschool.readthedocs.io`

## Estado da infraestrutura

- **Plataforma alvo: Azure** (créditos disponíveis, limitado a 80€/mês para esta PoC).
- Precisa de **domínio + HTTPS reais** (não só IP:porta) — é uma condição
  para a PoC, porque vamos ter utilizadores de teste reais, incluindo em
  mobile, e HTTPS é necessário para vários comportamentos de browser
  (cookies seguros, upload de fotos via câmara, etc.)
- **Azure MCP não tem credenciais válidas nesta máquina** (o PC do Pedro tem
  restrições administrativas que impedem `az login`/Azure CLI local — sem
  Azure CLI instalada, e todos os métodos de credencial do
  `ChainedTokenCredential` falham). O GitHub MCP, esse, está autenticado e
  com escrita (`pedrobsm`).
- **Por isso, o provisionamento é feito via Terraform a partir de outro PC**
  (onde o Pedro consegue autenticar-se no Azure). Ficheiros em
  `infra/terraform/` — ver `infra/terraform/README.md` para o passo-a-passo
  completo. Cria uma única VM Ubuntu 22.04 (Standard_B2s por omissão) com
  tudo integrado (web+huey+postgres+redis+nginx via Docker/Swarm), disco de
  dados separado em `/data`, e acesso SSH por chave (sem password auth,
  restrito por IP via `allowed_ssh_cidrs`).
- O Terraform provisiona a **infraestrutura** (VM, rede, firewall, Docker
  instalado, repo clonado) mas **não** corre `docker/setup_stack.sh`
  (interativo de propósito — swarm init, secrets, migrações). Isso faz-se
  manualmente por SSH depois do `terraform apply`. Notas de contexto ficam
  em `/opt/hopin/INFRA_NOTES.md` dentro da própria VM.
- **VM já criada e viva**: `vm-hopin-poc`, IP `20.126.64.224`, user
  `hopinadmin`, chave em `C:\Users\pedro\.ssh\hopin_vm_key` (neste PC, apesar
  de o `apply` ter corrido noutro). SSH confirmado a funcionar a partir
  desta máquina. Estado: Docker ativo, disco `/data` montado, swap 2GB, ufw
  + fail2ban ativos, repo em `/opt/hopin/app`.
- **Site em produção e funcional** (2026-08-24):
  `https://20-126-64-224.sslip.io/` responde 200 (django CMS welcome page),
  `/admin/login/` responde 200 com CSS a carregar (Django site admin).
  Certificado de produção real da Let's Encrypt, validado externamente
  (`SSL verify result: 0`, sem `-k`). Migrações aplicadas, `collectstatic`
  feito, superuser `admin` criado (password em
  `/opt/hopin/.superuser_credentials` na VM, `chmod 600` — muda-a depois de
  a leres), dados de demo criados via `create_demo_data`. `setupschool`
  (assistente interativo de nome/localização/timezone do negócio) **não foi
  corrido** — fica para quando os dados reais da HOP IN vierem do Gdrive
  (objetivo 3 da PoC).
- **Armadilha nova: manifesto do Whitenoise fica em cache no Gunicorn** — se
  corres `collectstatic` num container `web` que já estava a servir pedidos
  (gunicorn já arrancado), os workers mantêm o `staticfiles.json` antigo em
  memória e continuam a dar `ValueError: Missing staticfiles manifest
  entry` mesmo que o ficheiro e a entrada já existam em disco. **Fix**:
  depois de `collectstatic`, força sempre `docker service update --force
  danceschool_web` (ou equivalente) para os workers arrancarem de novo e
  lerem o manifesto atualizado.
- **cloud-init falhou no primeiro `apply` desta VM** (bug de parsing YAML
  no `runcmd:` + race condition no anexar do disco de dados) — já corrigido
  em `infra/terraform/cloud-init.yaml.tpl` e remediado manualmente por SSH
  na VM existente. Detalhes e um aviso importante (não corras `terraform
  apply`/`plan` sem cuidado nesta VM — mudou o `custom_data`, o que força
  recriação) em `infra/terraform/README.md`, secção "Problemas conhecidos".
- Stack: Docker Compose (web + huey + postgres + redis, mais nginx/caddy a
  acrescentar para TLS e para servir `/media/`).

## Coisas já aprendidas (não voltar a descobrir à custa de builds falhados)

O `production-template` oficial é pensado para Docker **Swarm**, com um
script `docker/setup_stack.sh` que cria secrets/volumes externos e faz build
local das imagens. No primeiro teste, nós adaptámos para um fluxo mais simples (standalone
Docker, sem Swarm), mas vamos voltar ao swarm pois esta opção teve as seguintes armadilhas:

1. **`docker/web/Dockerfile` usa `python:3.10-slim-bullseye`** — Bullseye já
   está EOL, os espelhos apt falham. **Já mudámos para
   `python:3.10-slim-bookworm`** neste fork.

2. **O Dockerfile original NUNCA copia a pasta `custom/` para a imagem** —
   só copia `custom/requirements.txt`. No design oficial isto funciona
   porque `custom/` é montado como *bind volume* a partir do host. Como
   construímos a imagem via CI (sem esse volume), é preciso adicionar
   explicitamente ao Dockerfile:
   ```dockerfile
   COPY ./custom/ /data/web/custom/
   ```
   (a seguir ao `pip3 install -r requirements_custom.txt`, antes do
   `ENV PYTHONPATH`). **Confirmar que esta linha está no Dockerfile atual.**

3. **`school/settings.py` — `INSTALLED_APPS`**: o `django-danceschool`
   pina `Django>=3.1.13,<3.2`, mas várias dependências no
   `requirements.txt`/`setup.py` não têm limite superior de versão, o que
   causa incompatibilidades quando o pip instala a versão mais recente.
   Pacotes já identificados e fixados em `custom/requirements.txt`:
   ```
   django-addanother
   django-cms<3.10
   django-admin-rangefilter<0.7
   django-multiselectfield==0.1.12
   ```
   Se aparecerem mais `ModuleNotFoundError` ou `AttributeError` deste tipo
   após um `pip install`, o padrão é sempre o mesmo: identificar o pacote,
   procurar no changelog dele quando é que a API mudou, e pinar a versão
   anterior compatível em `custom/requirements.txt`. Candidatos prováveis
   por não terem limite superior no `setup.py` do django-danceschool:
   `django-autocomplete-light`, os vários `djangocms_*`.

4. **App custom `democontent`**: criámos `custom/democontent/` (app Django
   simples, só com um management command) para gerar dados de demonstração.
   Está registada em `INSTALLED_APPS` como `'democontent',` — **atenção à
   vírgula**, já tivemos um `ModuleNotFoundError` por falta dela ao editar
   manualmente. Comando: `python3 manage.py create_demo_data` (idempotente,
   seguro correr mais do que uma vez). Cria: dance types (Lindy Hop, Blues),
   níveis, turmas, pricing, 2 locais no Porto, 3 instrutores, 3 séries de
   aulas (passada/atual/futura), e uma festa/evento social.

5. **Variáveis de ambiente / secrets**: `school/settings.py` lê
   `SECRET_KEY`/`DATABASE_URL` tanto de Docker secrets (`/run/secrets/...`)
   como de variáveis de ambiente simples (fallback). Não é preciso Swarm
   secrets — variáveis de ambiente normais no `docker-compose.yml` chegam.
   `ALLOWED_HOST` tem de corresponder ao domínio real depois de migrarmos
   para Azure.

6. **Media files**: com `DEBUG=False`, o Django não serve `/media/` sozinho
   (só estáticos, via Whitenoise). Isto ainda não está resolvido — é uma
   das primeiras coisas a tratar ao migrar para Azure com domínio, através
   de um Nginx/Caddy à frente do Gunicorn.

7. **GitHub write access**: confirmado — o Claude Code (GitHub MCP,
   autenticado como `pedrobsm`) tem escrita real neste repositório. A
   integração usada no chat do Claude.ai é que só tinha leitura (403 em
   `create_or_update_file`); isso não se aplica aqui.

8. **`docker/nginx/nginx.tmpl` não tinha location para
   `/.well-known/acme-challenge/`** — todo o tráfego HTTP (incluindo o
   desafio ACME) caía no `location /` e ia proxy para o Django, que devolve
   500 se as migrações não estiverem feitas (e 404 normal noutros casos) em
   vez de servir o ficheiro do desafio a partir do volume `html` partilhado.
   Isto bloqueava a emissão de certificado Let's Encrypt **sempre**,
   independentemente do domínio. **Corrigido**: adicionado
   `location /.well-known/acme-challenge/ { root /usr/share/nginx/html; ... }`
   nos dois server blocks de porta 80 (com e sem redirect para HTTPS), antes
   do `location /`. Confirmado a funcionar (certificado real de produção
   emitido para `20-126-64-224.sslip.io` na VM `vm-hopin-poc`).

9. **`huey` não deve incluir `env.web`** no `docker-compose.yml` — esse
   ficheiro tem `VIRTUAL_HOST`/`VIRTUAL_PORT`/`LETSENCRYPT_HOST`, variáveis
   que o nginx-proxy usa para descobrir containers a colocar no upstream. O
   huey não serve HTTP nenhum, mas ao herdar essas variáveis o nginx-proxy
   metia-o na mesma pool de upstream do `web`, causando 502/503
   intermitentes sempre que o load balancing calhava no huey. **Corrigido**:
   huey agora só carrega `env.default`.

   **Lembrete para o próximo passo (migrações)**: depois de correr
   `python3 manage.py migrate` dentro do container `web`, força um
   redeploy/restart do `nginx`/`letsencrypt-companion` não é necessário —
   só o `web` deixa de dar 500. Mas se voltares a mexer no
   `docker/nginx/nginx.tmpl` ou no `docker-compose.yml`, lembra-te que o
   Swarm **não** deteta sozinho que uma imagem local com a mesma tag
   (`:latest`) mudou — depois de `docker build`, usa
   `docker service update --force <serviço>` para forçar o redeploy da
   tarefa (ou volta a `docker stack deploy`, que também funciona se algum
   valor do spec do serviço mudou, como env vars).

## Acesso a contexto adicional

- **Google Drive da HOP IN**: usar o MCP do Google Drive (autenticar se
  necessário) para consultar documentos da associação (missão, identidade
  visual navy/dourado, conteúdos para páginas do site, composição das turmas de aulas etc.) em vez de
  inventar conteúdo. Pasta raiz partilhada a partir de
  `hopindancecommunity@gmail.com`.

## Objetivo desta fase (PoC)

1. Estabilizar um deploy novo em Azure com domínio + HTTPS reais.
2. Resolver a limitação de media files.
3. Gerar novos dados de demonstração mais reais, com base no documentos do Gdrive e aplicar branding básico da HOP IN.
4. Criar 7-8 contas de teste com papéis diferentes (admin, instrutor, voluntário, 3 alunos, financeiro, gestor de eventos) para avaliação por utilizadores reais.
5. Ficar pronto para avaliar: intuitividade, UX mobile, facilidade de
   customização visual, facilidade em interface biligue (PT/ES), facilidade de desenvolver módulos custom (ex. integração com pagamentos MBWay.

## Preferências de trabalho

- Sempre que resolveres um problema novo de compatibilidade de pacotes,
  Dockerfile, ou settings, **atualiza este ficheiro** com o que aprendeste,
  para a próxima sessão não repetir o mesmo trabalho de diagnóstico e apaga tudo o que deixa de fazer sentido.
- Comunica em português europeu ao resumir o que fizeste.
- Prefere fazer commits pequenos e frequentes com mensagens claras, em vez
  de um commit gigante no fim.
- Deixei um branch (Saved_before_azure_and_swarm) criado para salvaguardar o trabalho anterior. Se achares por bem começar de novo por por voltarmos ao docker swarm, podes fazer novo pull/fork desde o repo original.
