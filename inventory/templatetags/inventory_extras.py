from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """Multiply the arg by the value"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    """Divide the value by the arg"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def add_class(field, css_class):
    """Add a CSS class to a Django form field"""
    attrs = field.field.widget.attrs
    if 'class' in attrs:
        attrs['class'] += f" {css_class}"
    else:
        attrs['class'] = css_class
    return field

@register.filter
def add_error_class(field, css_class):
    """Add an error class to a Django form field if it has errors"""
    if hasattr(field, 'errors') and field.errors:
        return add_class(field, css_class)
    return field 