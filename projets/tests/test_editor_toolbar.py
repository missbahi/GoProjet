from django.template import Context, Template
from django.test import SimpleTestCase


class EditorToolbarTagTests(SimpleTestCase):
    def test_toolbar_et_groupes_reutilisent_la_charte(self):
        rendu = Template(
            """
            {% load editor_toolbar %}
            {% editor_toolbar "Actions" "ca-selection-toolbar" %}
              {% toolbar_group "Affichage" %}
                <button type="button">Ouvrir</button>
              {% end_toolbar_group %}
            {% end_editor_toolbar %}
            """
        ).render(Context())

        self.assertIn('class="editor-toolbar ca-selection-toolbar"', rendu)
        self.assertIn('role="toolbar" aria-label="Actions"', rendu)
        self.assertIn('class="editor-toolbar__group "', rendu)
        self.assertIn('role="group" aria-label="Affichage"', rendu)
        self.assertIn("<button", rendu)

