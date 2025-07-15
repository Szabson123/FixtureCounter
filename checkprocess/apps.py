from django.apps import AppConfig


class CheckprocessConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'checkprocess'

    def ready(self):
        import checkprocess.signals