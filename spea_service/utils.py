from django.conf import settings


polmesprod_database_string = (
    f'DRIVER={{ODBC Driver 17 for SQL Server}};'
    f"SERVER={settings.POLMESPROD_HOST};"
    f"DATABASE={settings.POLMESPROD_DATABASE_NAME};"
    f"UID={settings.POLMESPROD_USER};"
    f"PWD={settings.POLMESPROD_PASSWORD}"
)