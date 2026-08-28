# Django >= 3.2 deteta sozinho a única AppConfig definida em apps.py
# (HopinThemeConfig) — não precisa de `default_app_config` aqui. Essa linha
# só era necessária no Django 3.1 (CLAUDE.md, armadilha 21); no Django 5.2
# é código morto inofensivo, mas removido por limpeza.
