"""The DEMO_MODE guard: demo mode may only run on this machine, with the demo SMS inbox.

`demo_mode_problems` is a pure function over settings-like values, so settings can call it at
import time (refusing to start) and the `demo_mode_check` system check can report it too.
Nothing here imports the `demo` app: the demo sender is named only by its dotted path.
"""

DEMO_MODE_MESSAGE = "DEMO_MODE may only run on localhost with the demo SMS inbox."
DEMO_SENDER = "demo.sender.DemoInboxOtpSender"
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "[::1]"})


def demo_mode_problems(settings) -> list[str]:
    if not getattr(settings, "DEMO_MODE", False):
        return []
    problems = []
    foreign = [host for host in settings.ALLOWED_HOSTS if host not in LOCAL_HOSTS]
    if foreign:
        problems.append(f"ALLOWED_HOSTS has hosts other than localhost: {', '.join(foreign)}")
    if settings.SECURE_SSL_REDIRECT:
        problems.append("DJANGO_SSL_REDIRECT is on")
    if settings.OTP_SENDER != DEMO_SENDER:
        problems.append(f"OTP_SENDER is not {DEMO_SENDER}")
    return problems


def demo_mode_check(app_configs, **kwargs) -> list:
    """System check (registered by the demo app): the same guard, for `manage.py check`.

    Django is imported here, not at module level, because settings import this module.
    """
    from django.conf import settings
    from django.core.checks import Error

    problems = demo_mode_problems(settings)
    return [Error(DEMO_MODE_MESSAGE, hint="; ".join(problems))] if problems else []
