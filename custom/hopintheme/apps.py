from django.apps import AppConfig


class HopinThemeConfig(AppConfig):
    name = 'hopintheme'
    verbose_name = 'HOP IN Theme Overrides'

    def ready(self):
        patch_staff_member_list_plugin()


def patch_staff_member_list_plugin():
    '''
    Monkeypatch para um bug do django-multiselectfield (== 0.1.12, ver
    CLAUDE.md item 3 e item 11) no campo `statusChoices` de
    `StaffMemberListPlugin` (danceschool.core.cms_plugins).

    Confirmado em produção (2026-08-25): quando um editor marca qualquer
    combinação de checkboxes em "Limit to Instructors with Status" e grava
    via o admin, o valor que `render()` recebe em
    `instance.statusChoices` vem como os RÓTULOS legíveis ("Regular
    Instructor", "Assistant Instructor", ...) em vez das chaves reais
    ("R", "A", ...) guardadas na coluna `Instructor.status`. O filtro
    `instructor__status__in=[rótulos]` não bate certo com nenhuma linha
    real, e a lista de instrutores fica vazia — sem erro nenhum, silencioso.

    Pior: o campo é obrigatório no formulário do admin (não dá para
    gravar com tudo por marcar), por isso a única forma de configurar
    este plugin através da interface fica permanentemente quebrada — não
    há nenhuma combinação de checkboxes que funcione sem este patch.

    Em vez de editar o pacote vendorizado (perder-se-ia num rebuild),
    interceptamos `render()` aqui e normalizamos `statusChoices` de volta
    para chaves reais antes do filtro correr, aceitando tanto chaves como
    rótulos (não sabemos ao certo em que condições cada representação
    aparece, por isso aceitamos as duas).
    '''
    from danceschool.core.cms_plugins import StaffMemberListPlugin
    from danceschool.core.models import Instructor

    original_render = StaffMemberListPlugin.render

    def patched_render(self, context, instance, placeholder):
        if instance.statusChoices:
            label_to_key = {
                label: key for key, label in Instructor.InstructorStatus.choices
            }
            valid_keys = set(label_to_key.values())
            instance.statusChoices = [
                item if item in valid_keys else label_to_key.get(item, item)
                for item in instance.statusChoices
            ]
        return original_render(self, context, instance, placeholder)

    StaffMemberListPlugin.render = patched_render
