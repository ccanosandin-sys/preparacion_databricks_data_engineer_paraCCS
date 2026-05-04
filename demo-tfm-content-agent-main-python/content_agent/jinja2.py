from jinja2 import Environment


def environment(**options):
    """
    Entorno Jinja2 para Django.
    Django inyecta automáticamente csrf_input, csrf_token y request en el contexto.
    """
    env = Environment(**options)
    return env
