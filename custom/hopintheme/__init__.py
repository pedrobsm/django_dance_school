# Django 3.1 (a versão pinada neste projeto) não tem a deteção automática
# de AppConfig introduzida no Django 3.2 — sem esta linha, o Django ignora
# HopinThemeConfig (definida em apps.py) e usa uma AppConfig genérica cujo
# ready() não faz nada, silenciosamente. custom/hopintheme/apps.py depende
# de ready() correr (faz um monkeypatch necessário), por isso esta linha é
# obrigatória aqui — ver CLAUDE.md para o contexto completo.
default_app_config = 'hopintheme.apps.HopinThemeConfig'
