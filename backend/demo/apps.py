from django.apps import AppConfig
from django.core import checks


class DemoConfig(AppConfig):
    name = "demo"

    def ready(self) -> None:
        from config.checks import demo_mode_check

        checks.register(demo_mode_check, checks.Tags.security)
