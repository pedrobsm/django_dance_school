# HOP IN — django-danceschool — Contexto do Projeto

## O que é isto

A HOP IN é uma associação de dança Swing e Blues no Porto, Portugal. Este
repositório é um fork de `django-danceschool/production-template`, usado para
gerir inscrições em aulas (mensalidades) e eventos/festas (bilhética),
incluindo um fluxo com três papéis: administradores (criam aulas/eventos),
alunos/participantes (inscrevem-se), e voluntários (confirmam presenças e
pagamentos).

Este é atualmente um **PoC** para avaliar se esta plataforma serve a
associação — não é ainda produção real. Comunicação sobre a HOP IN é em
**português europeu**.

- Fork: `github.com/pedrobsm/django_dance_school`
- Upstream original: `github.com/django-danceschool/production-template`
- Documentação do projeto: `django-danceschool.readthedocs.io`

## Estado da infraestrutura

- **Plataforma alvo: Azure** (créditos disponíveis, sem restrição de custo
  para esta PoC). Ainda por provisionar/finalizar nesta sessão.
- Precisa de **domínio + HTTPS reais** (não só IP:porta) — é uma condição
  para a PoC, porque vamos ter utilizadores de teste reais, incluindo em
  mobile, e HTTPS é necessário para vários comportamentos de browser
  (cookies seguros, upload de fotos via câmara, etc.)
- Acesso à Azure disponível via **Azure MCP** (ferramentas MCP já
  configuradas nesta sessão) — usa-as para provisionar/gerir recursos em vez
  de pedir credenciais ou assumir CLI local não autenticado.
- Stack: Docker Compose (web + huey + postgres + redis, mais nginx/caddy a
  acrescentar para TLS e para servir `/media/`).

## Coisas já aprendidas (não voltar a descobrir à custa de builds falhados)

O `production-template` oficial é pensado para Docker **Swarm**, com um
script `docker/setup_stack.sh` que cria secrets/volumes externos e faz build
local das imagens. Nós adaptámos para um fluxo mais simples (standalone
Docker, sem Swarm), e isto teve as seguintes armadilhas:

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

7. **GitHub write access**: a integração usada no chat do Claude.ai só tinha
   leitura neste repositório (todas as tentativas de `create_or_update_file`
   deram 403), por isso todas as alterações até agora foram feitas
   manualmente pelo Pedro. **O Claude Code, autenticado via `gh auth
   login`, deve ter escrita real** — confirmar isto logo no arranque.

## Acesso a contexto adicional

- **Google Drive da HOP IN**: usar o MCP do Google Drive (autenticar se
  necessário) para consultar documentos da associação (missão, identidade
  visual navy/dourado, conteúdos para páginas do site, etc.) em vez de
  inventar conteúdo. Pasta raiz partilhada a partir de
  `hopindancecommunity@gmail.com`.

## Objetivo desta fase (PoC)

1. Estabilizar o deploy em Azure com domínio + HTTPS reais.
2. Resolver a limitação de media files.
3. Popular com dados de demonstração e aplicar branding básico da HOP IN.
4. Criar 3-4 contas de teste com papéis diferentes (admin, instrutor/
   voluntário, aluno) para avaliação por utilizadores reais.
5. Ficar pronto para avaliar: intuitividade, UX mobile, facilidade de
   customização visual, facilidade de desenvolver módulos custom.

## Preferências de trabalho

- Sempre que resolveres um problema novo de compatibilidade de pacotes,
  Dockerfile, ou settings, **atualiza este ficheiro** com o que aprendeste,
  para a próxima sessão não repetir o mesmo trabalho de diagnóstico.
- Comunica em português europeu ao resumir o que fizeste.
- Prefere fazer commits pequenos e frequentes com mensagens claras, em vez
  de um commit gigante no fim.
