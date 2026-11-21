from django import template
from django.utils.html import format_html


register = template.Library()


class EditorToolbarNode(template.Node):
    def __init__(self, nodelist, label, extra_classes):
        self.nodelist = nodelist
        self.label = label
        self.extra_classes = extra_classes

    def render(self, context):
        label = self.label.resolve(context)
        extra_classes = (
            self.extra_classes.resolve(context) if self.extra_classes else ""
        )
        return format_html(
            '<div class="editor-toolbar {}" role="toolbar" aria-label="{}">{}</div>',
            extra_classes,
            label,
            self.nodelist.render(context),
        )


class EditorToolbarGroupNode(template.Node):
    def __init__(self, nodelist, label, extra_classes):
        self.nodelist = nodelist
        self.label = label
        self.extra_classes = extra_classes

    def render(self, context):
        label = self.label.resolve(context)
        extra_classes = (
            self.extra_classes.resolve(context) if self.extra_classes else ""
        )
        return format_html(
            '<div class="editor-toolbar__group {}" role="group" aria-label="{}">{}</div>',
            extra_classes,
            label,
            self.nodelist.render(context),
        )


@register.tag
def editor_toolbar(parser, token):
    bits = token.split_contents()
    if len(bits) not in (2, 3):
        raise template.TemplateSyntaxError(
            "{% editor_toolbar 'Libellé' 'classes-optionnelles' %}"
        )
    nodelist = parser.parse(("end_editor_toolbar",))
    parser.delete_first_token()
    return EditorToolbarNode(
        nodelist,
        parser.compile_filter(bits[1]),
        parser.compile_filter(bits[2]) if len(bits) == 3 else None,
    )


@register.tag
def toolbar_group(parser, token):
    bits = token.split_contents()
    if len(bits) not in (2, 3):
        raise template.TemplateSyntaxError(
            "{% toolbar_group 'Libellé' 'classes-optionnelles' %}"
        )
    nodelist = parser.parse(("end_toolbar_group",))
    parser.delete_first_token()
    return EditorToolbarGroupNode(
        nodelist,
        parser.compile_filter(bits[1]),
        parser.compile_filter(bits[2]) if len(bits) == 3 else None,
    )
