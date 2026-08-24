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
  a leres), dados de demo criados via `create_demo_data` e via
  `create_hopin_demo_data` (dados aproximados do plano real 2025/26 +
  workshops de Setembro, ver secção "Dados de demonstração" abaixo).
  **`setupschool` foi corrido** (manualmente por SSH, fora desta sessão) —
  criou as páginas standard (Home, Instructors, Calendar, FAQ, Login,
  etc.) e por acaso destronou a homepage que o `create_hopin_demo_data`
  tinha criado (ver item 12 da lista de armadilhas). Ainda por confirmar
  se os valores que o `setupschool` pediu (nome da escola, timezone, etc.)
  são os reais da HOP IN ou só placeholders de teste.
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

10. **`TIME_ZONE` no `env.default` estava em `America/New_York`** (default
    do template upstream, nunca tinha sido alterado). Todos os horários de
    turmas/workshops são inseridos em hora de Portugal — com o fuso errado,
    apareceriam desfasados várias horas. **Corrigido**: `Europe/Lisbon`.

11. **`StaffMemberListPlugin` (página "Professores") não mostrava
    ninguém** — o campo `statusChoices` (`django-multiselectfield`, mesmo
    pacote com histórico de problemas, ver item 3) tem um valor por omissão
    não-vazio (`['R','A','G']`). Quando não-vazio, `render()` do plugin faz
    `StaffMember.objects.filter(instructor__status__in=instance.statusChoices)`
    — mas o `MSFList` devolvido pelo `MultiSelectField` faz o Django ORM
    gerar um `EmptyResultSet` neste `__in` (bug de compatibilidade, não do
    nosso código). Quando o campo fica vazio (`falsy`), o plugin usa antes
    `.exclude(instructor__status__in=[lista Python normal])`, que funciona
    bem. **Fix**: passar sempre `statusChoices=[]` explicitamente ao criar
    este plugin via `cms.api.add_plugin` (feito em
    `create_hopin_demo_data.py`). Se voltares a ver a página de professores
    vazia apesar de existirem `Instructor` com `status=roster`, é este bug.

12. **`create_hopin_demo_data` criava uma segunda homepage** — a primeira
    versão do comando criava sempre uma página nova "HOP IN" e chamava
    `set_as_homepage()`. Quando o `setupschool` foi corrido depois (na VM,
    manualmente por SSH), criou a sua própria página "Home" e roubou-lhe o
    estado de homepage — ficaram duas páginas parecidas com homepage, uma
    órfã ("HOP IN", com o manifesto, já sem `is_home`) e outra ativa
    ("Home", com o texto genérico de boas-vindas do `setupschool`).
    **Corrigido no script** (ainda não aplicado na VM, só no repo — ver
    abaixo): agora procura a página que já É a homepage
    (`Page.objects.filter(is_home=True, publisher_is_draft=True).first()`)
    e escreve o manifesto nos placeholders *dessa* página, só criando uma
    nova se não existir nenhuma homepage. Limpa plugins antigos do
    placeholder antes de inserir o manifesto, por isso é seguro re-correr.
    **Nota**: a VM continua com a página "HOP IN" órfã por apagar — só
    fazer isso (apagá-la manualmente ou re-correr o comando corrigido)
    quando for pedido explicitamente.

13. **Seletor de idioma não pode usar POST** — o django-cms tem cache de
    página ligada por omissão (`CMS_PAGE_CACHE`, `Cache-Control:
    max-age=60`). Uma resposta servida da cache leva embutido o token CSRF
    de quem a renderizou primeiro e **não** traz `Set-Cookie: csrftoken`,
    por isso um POST do visitante é validado contra um token que não é dele
    → **403 intermitente**. Confirmado ao vivo: um GET em cache devolveu só
    `django_language`, sem `csrftoken`. **Solução**: o seletor troca de
    idioma por **link GET** (tag `switch_language_url` em
    `custom/hopintheme/templatetags/hopin_i18n.py`), que dispensa CSRF e é
    seguro em cache. Funciona porque as rotas públicas estão dentro de
    `i18n_patterns` — o próprio URL identifica o idioma, não é preciso
    estado no servidor. **Regra geral**: qualquer formulário POST em páginas
    CMS públicas sofre do mesmo problema; preferir GET ou desligar a cache
    para essa página.

14. **`makemessages` precisa da pasta `locale/` criada antes** — senão dá
    `CommandError: Unable to find a locale path to store translations`. O
    catálogo do `django-danceschool` foi extraído a correr
    `django-admin makemessages -l pt` *dentro* de
    `site-packages/danceschool/` (2302 msgids) e depois copiado para
    `locale/pt/LC_MESSAGES/django.po` do projeto. Isto funciona porque
    `LOCALE_PATHS` tem prioridade sobre os catálogos das apps instaladas —
    traduz o pacote sem lhe tocar em `site-packages`.
    **Não corras `makemessages` ao nível do projeto por cima deste
    ficheiro**: as strings do danceschool não existem no código do projeto,
    seriam marcadas obsoletas (ou removidas com `--no-obsolete`).
    Os `.mo` **não** vão para o git (já em `.gitignore`); são compilados no
    build da imagem com `msgfmt` (ver `docker/web/Dockerfile`) — usa-se
    `msgfmt` direto e não `manage.py compilemessages` porque este último
    carrega o `settings.py` completo, que precisa de `DATABASE_URL`/
    `SECRET_KEY`, coisas que não existem durante o build.

15. **Ordem entre `create_hopin_demo_data` e `translate_cms_pages`** — os
    dois escrevem o manifesto da homepage (o primeiro numa variante sem
    acentos, o segundo com acentos e nos dois idiomas). Corre sempre
    `create_hopin_demo_data` **primeiro** e `translate_cms_pages`
    **depois**. Vale a pena unificar os dois textos num módulo partilhado
    quando o conteúdo real da HOP IN estabilizar.

19. **`default_settings.py` do pacote `danceschool` instancia um `SqliteHuey`
    com efeitos secundários reais só por ser importado** — `school/settings.py`
    faz `from danceschool.default_settings import *` e só depois sobrepõe
    `HUEY = RedisHuey(...)`, mas o `SqliteHuey(...)` do meio já correu e
    tentou abrir/inicializar um ficheiro `huey.sqlite3` local nesse instante,
    antes de ser descartado. Isto é inofensivo isoladamente, mas se dois
    processos arrancam ao mesmo tempo (os 2 workers do Gunicorn, ou o
    container `web` e o `huey` em simultâneo, ou durante um restart) podem
    colidir nesse `SqliteHuey.__init__` e um deles crasha no arranque com
    `sqlite3.OperationalError: database is locked` (mata o processo Python
    inteiro, antes do Django sequer carregar — não é um erro do Huey em uso,
    é só a inicialização acidental). **Confirmado no branch vanilla** (ver
    secção abaixo) ao forçar `docker service update --force danceschool_web`
    logo a seguir ao deploy — a tarefa falhou uma vez e o Swarm
    reiniciou-a automaticamente com sucesso (comportamento "any" do restart
    policy). **Não é um bug nosso nem específico da HOP IN** — é
    comportamento do próprio `danceschool.default_settings`, herdado desde o
    fork. Se voltar a acontecer: não entrar em pânico, o Swarm normalmente
    autorrecupera; se não recuperar sozinho, tenta outro
    `docker service update --force` (a colisão é por timing, raramente
    repete duas vezes seguidas).

## Teste vanilla (Hetzner) — comparação sem alterações HOP IN

**Objetivo**: perceber o comportamento do `django-danceschool` "de fábrica"
(sem paleta de cores, sem i18n PT/EN, sem dados de demo da HOP IN, sem
`democontent`) para conseguir distinguir bugs upstream de problemas
introduzidos pelas nossas customizações. Pedido em 2026-08-24.

- **Branch**: `vanilla/hetzner-media-poc`, criado a partir do commit exato
  onde o fork começou (`0732c93`, o último commit do upstream Lee Tucker
  antes do primeiro commit do `pedrobsm`) — **zero** alterações estéticas,
  i18n, ou de conteúdo. Só têm 8 commits em cima do fork, todos correções de
  infraestrutura/compatibilidade genuínas (não específicas da HOP IN,
  seriam precisas em qualquer deploy feito hoje):
  - Fix Debian sources + mudança para `python:3.10-slim-bookworm`
  - Pins de versão (`django-cms`, `django-addanother`,
    `django-admin-rangefilter`, `django-multiselectfield`) — mesmo problema
    do item 3 acima, reaparece em qualquer build feito em 2026
  - O fix do `/.well-known/acme-challenge/` (item 8 acima)
  - O fix do `huey`/`env.web` (item 9 acima)
  - Fix novo, só neste branch: `location /media` também faltava no bloco
    HTTP simples do `nginx.tmpl` (só existia no bloco HTTPS) — mesma classe
    de bug do item 8, adicionado por paridade.
  - **Não inclui**: `democontent`/`create_demo_data`, `create_hopin_demo_data`,
    paleta de cores, dark mode, i18n PT/EN, fixes de admin/favicon ligados
    ao i18n. O site fica com o conteúdo puramente genérico do
    `django-danceschool` (sem `setupschool` corrido também).
- **VM**: Hetzner, IP `77.42.45.222`, user **`root`** (não `hopinadmin` — a
  imagem Hetzner não tem esse user), mesma chave SSH
  (`C:\Users\pedro\.ssh\hopin_vm_key`). Ubuntu 26.04 LTS. Volume de bloco de
  10GB já vinha anexado e montado em `/mnt/volume-media-hel1` antes desta
  sessão.
- **Volume de media**: o `docker-compose.yml` deste branch já não usa
  `media: external: true` — passou a `driver: local` com `driver_opts`
  (`type: none, o: bind, device: /mnt/volume-media-hel1/media`), ou seja, o
  volume nomeado do Docker é agora um bind direto ao disco anexado.
  **Confirmado a funcionar de ponta a ponta**: ficheiro escrito pelo Django
  em `MEDIA_ROOT` (`/data/web/school/media/...`) aparece imediatamente em
  `/mnt/volume-media-hel1/media/...` no host, e é servido corretamente via
  `https://77-42-45-222.sslip.io/media/...` (200).
- **Site em produção e funcional**: `https://77-42-45-222.sslip.io/` e
  `/admin/login/` respondem 200, certificado real da Let's Encrypt validado
  externamente. Superuser `admin` criado (password em
  `/opt/hopin/.superuser_credentials` na VM). Sem dados de demo — o site
  mostra o estado "vazio" genérico do django-cms/danceschool.
- **Achado**: a colisão `SqliteHuey`/`database is locked` no arranque (item
  19 acima) foi descoberta aqui, ao forçar um restart do `web` logo a
  seguir ao deploy. Autorrecuperou sozinha via Swarm.
- **Imagens Docker**: construídas **localmente na VM** a partir do código
  deste branch (`docker build`), **não** usar a imagem `ghcr.io/pedrobsm/
  danceschool-web:latest` — essa é publicada por CI a partir do `master` e
  já traz todas as customizações da HOP IN, o que anularia o propósito do
  teste.
- **Por fazer**: comparação lado-a-lado com o deploy Azure/master
  (`https://20-126-64-224.sslip.io/`) para identificar diferenças de
  comportamento atribuíveis às nossas alterações.

## Internacionalização (PT/EN)

**Integrado em `master` e no ar** (2026-08-24). O branch
`feature/i18n-pt-en` já foi merged; a VM corre `master` e a imagem
`danceschool_web:latest` é construída a partir dele. A imagem anterior
ficou guardada como `danceschool_web:pre-i18n` e há um dump da BD em
`/data/backups/pre-i18n-*.sql`, caso seja preciso reverter.

- **Configuração**: `LANGUAGE_CODE='pt'` (sobreponível por env), `LANGUAGES`
  PT/EN, `CMS_LANGUAGES` com fallback mútuo (`hide_untranslated: False`), e
  `LOCALE_PATHS` a apontar para `locale/` na raiz do projeto. Sem isto o
  projeto herdava `LANGUAGES = [('en', 'English')]` do
  `danceschool.default_settings` — i18n estava meio ligado (`USE_I18N` e
  `LocaleMiddleware` já lá estavam) mas com um só idioma.
- **URLs**: tudo dentro de `i18n_patterns` → `/pt/...` e `/en/...`,
  **incluindo o `admin/`**; `/` redireciona conforme o `Accept-Language`.
  Só as vistas `i18n/` (set_language) e o `/favicon.ico` ficam sem prefixo.
  Nota: isto também prefixa o `sitemap.xml` e os URLs do django-filer que
  vêm dentro de `danceschool.urls` — não é o convencional para o sitemap,
  mas são todos resolvidos por `reverse()`, por isso funcionam.

16. **O `admin/` TEM de estar dentro do `i18n_patterns`** — na primeira
    versão deixei-o fora, a raciocinar que o admin não precisa de prefixo
    de idioma. Errado: é o que o template oficial de projeto do django-cms
    faz, e a barra de ferramentas do CMS constrói links de admin
    **relativos à página atual**, ou seja com prefixo. Com o admin fora,
    esses links saíam `/en/admin/core/staffmember/` e davam **404**
    (apanhado nos logs do nginx, não nos do Django — o 404 nem chega a
    gerar traceback). `/admin/` sem prefixo continua a funcionar via
    redirect do `LocaleMiddleware`. Efeito lateral bom: o idioma do admin
    passa a vir do URL em vez do cookie, o que o torna previsível.

17. **`/favicon.ico` precisa de rota própria** — o browser pede-o na raiz
    por sua conta; sem rota, cai no `i18n_patterns`, ganha prefixo e acaba
    em `/en/favicon.ico/` → 404. Resolvido com um `RedirectView` para o
    ficheiro em `static/`.

18. **Onde procurar erros**: os 404 de routing **não** aparecem nos logs do
    Django (`docker service logs danceschool_web`) — só nos do nginx
    (`docker service logs danceschool_nginx`). Ao investigar "links que não
    funcionam", começa sempre pela distribuição de status do nginx:
    ```bash
    docker service logs danceschool_nginx --since 2h 2>&1 \
      | grep sslip.io | grep -oE '" [0-9]{3} ' | sort | uniq -c | sort -rn
    ```

19. **Os calendários não respeitam o i18n do Django** — são desenhados no
    browser pelo FullCalendar/moment.js, por isso `LANGUAGE_CODE`/`USE_L10N`
    não lhes chegam (só afetam render do lado do servidor). O upstream não
    define formato nem passa locale → o FullCalendar assume inglês e
    **relógio de 12 horas (AM/PM)**, e o popup do evento tinha
    `'MMM Do h:mm A'` escrito à mão no template. Não dá para resolver com
    `locale: 'pt'`: o danceschool só distribui o `fullcalendar.min.js` e o
    `moment.min.js` base, sem ficheiros de locale. **Corrigido** com
    `timeFormat`/`slotLabelFormat` a `'H:mm'` e um formato por idioma no
    popup, em dois overrides:
    - `custom/hopintheme/templates/core/public_calendar.html` (público)
    - `custom/hopintheme/templates/private_events/private_fullcalendar.html`
      (staff) — este é uma **cópia de 235 linhas** do template upstream com
      apenas 3 alterações; se atualizares o `django-danceschool`, compara
      com o original e re-aplica só essas três. O ficheiro diz isto no topo.
    Em PT usa-se data numérica (`DD/MM/AAAA`) de propósito: além de ser a
    convenção portuguesa, evita o moment cair em nomes de meses ingleses
    por falta de dados de locale.
- **Slugs por idioma**: `/pt/calendario/` e `/en/calendar/` são a mesma
  página. Os slugs **ingleses** das páginas criadas pelo
  `create_hopin_demo_data` ficaram em português (`professores`, `turmas`) —
  só o título visível foi corrigido para inglês, o slug não, para não mudar
  URLs. Se quiseres alinhar, é uma alteração simples na UI do CMS.
- **Cobertura da tradução de UI**: 330 de 2302 strings — todo o percurso
  público (inscrição, aulas, eventos, carrinho, faturas, conta, check-in,
  labels e erros de formulários). O back-office financeiro/admin/relatórios
  está **por traduzir de propósito**: só a equipa o vê e triplicava o
  trabalho de revisão sem ganho para a PoC. Para continuar, é só preencher
  mais `msgstr` no `.po` e reconstruir a imagem.
- **Traduzir páginas CMS**: `python3 manage.py translate_cms_pages`
  (idempotente). Cria títulos/slugs PT, copia conteúdo EN→PT nas páginas sem
  versão PT, corrige títulos EN que estavam em português, escreve o
  manifesto da homepage nos dois idiomas e publica ambos. Cobre também os
  static placeholders (rodapé).
- **Registo de tratamento**: informal ("tu"), consistente com o tom do
  documento *Brand Compass* da HOP IN.
- **Por rever por um humano**: a versão **inglesa** do manifesto da homepage
  é uma tradução do texto português existente, feita pelo Claude — deve ser
  revista por alguém da HOP IN antes de ir para produção real.

## Dados de demonstração

- `python3 manage.py create_demo_data` — dados genéricos (Maria Silva,
  João Santos, etc.), ver secção acima.
- `python3 manage.py create_hopin_demo_data` — dados aproximados do plano
  pedagógico real da HOP IN 2025/26 e dos workshops de Setembro 2026
  (fonte: spreadsheet "Plano Pedagógico" e pasta de workshops no Google
  Drive da associação — não copiados para o repo, só lidos). Cria tipos de
  dança/níveis, instrutores (com os nomes reais mencionados no plano),
  preços (mensalidade par/solo, workshop), 7 turmas regulares e os 5
  workshops "HOP INto..." de Setembro com datas/preços/professores reais e
  descrições retiradas do documento de workshops. Cria também páginas CMS:
  injeta o manifesto de marca resumido na homepage já existente (ver item
  12 acima — não cria uma segunda homepage), mais "Professores" e "Turmas"
  (calendário público). Ambos os comandos são complementares e
  idempotentes (podes correr os dois, e
  corrê-los outra vez não duplica dados).
  Detalhes que ficaram por resolver/simplificados de propósito (PoC): o
  `setupschool` (nome/localização/timezone do negócio) continua por
  correr; a rotação de professores por módulo mensal não está modelada
  (fica só o professor "principal"); datas exatas do arranque da época
  regular 2025/26 não estavam decididas no plano, por isso usámos a
  próxima 3ª/4ª/6ª-feira a partir da data em que o comando corre, em vez
  de Outubro fixo.

## Acesso a contexto adicional

- **Google Drive da HOP IN**: usar o MCP do Google Drive (autenticar se
  necessário) para consultar documentos da associação (missão, identidade
  visual, conteúdos para páginas do site, composição das turmas de aulas
  etc.) em vez de inventar conteúdo. Pasta raiz partilhada a partir de
  `hopindancecommunity@gmail.com`.
- **Correção (2026-08-24): não há ainda paleta de cores oficial definida.**
  A nota anterior aqui ("navy/dourado") estava desatualizada/incorreta —
  verificado no Drive: `Proposta Brand Compass` (doc, 11/08/2026, o
  documento de posicionamento mais recente) diz explicitamente que a
  identidade visual concreta **ainda não foi decidida**, e pede o oposto de
  navy/dourado — "uma paleta que fuja das cores corporativas ou demasiado
  sérias", personalidade **warm/welcoming/playful/friendly/curious**,
  "colorido, expressivo, com cor, calor e energia". `Brand Comparison.xlsx`
  e `Estudo de Branding_ Marta.pdf` são pesquisa de concorrência (cores de
  *outras* escolas de swing, para inspiração), não a paleta da HOP IN. O
  PDF tem mood boards com swatches em imagem que a leitura por texto do MCP
  não consegue extrair — se precisares mesmo das cores exatas desses
  boards, é preciso ver o PDF visualmente. **Antes de aplicar qualquer
  paleta "oficial" ao site, confirma com o Pedro** — não presumir navy/
  dourado nem inventar cores "definitivas" sem confirmação.

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
