import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


load_dotenv(os.path.join(BASE_DIR, '.env'))

# PASSWORDS
CLEAR_COUNTER_PASSWORD = os.getenv('CLEAR_COUNTER_PASSWORD')
VARIANT_SECRET_PASSWORD = os.getenv('VARIANT_SECRET_PASSWORD')


SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY is missing from environment variables!")


DEBUG = True

ALLOWED_HOSTS = ['10.140.113.33', 'localhost', '127.0.0.1']


EXTERNAL_SQL_SERVER = os.getenv('EXTERNAL_SQL_SERVER')
EXTERNAL_SQL_DB = os.getenv('EXTERNAL_SQL_DB')
EXTERNAL_SQL_USER = os.getenv('EXTERNAL_SQL_USER')
EXTERNAL_SQL_PASSWORD = os.getenv('EXTERNAL_SQL_PASSWORD')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'drf_spectacular',
    'corsheaders',
    'django_eventstream',
    'django_filters',
    
    # My
    'base',
    'map',
    'goldensample',
    'checkprocess',
    # 'user_auth',
]

CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django_grip.GripMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STATIC_URL = "/static/"

EVENTSTREAM_ALLOW_ORIGIN = '*'

ROOT_URLCONF = 'MachineFixture.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'MachineFixture.wsgi.application'


CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

USE_I18N = True

TIME_ZONE = 'Europe/Warsaw'
USE_TZ = True


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Your Project API',
    'DESCRIPTION': 'Your project description',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    # OTHER SETTINGS
}

DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000


CSRF_TRUSTED_ORIGINS = [
    'http://10.140.113.33',
]

REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
        'rest_framework.filters.SearchFilter',
    ],
    
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',

    # "DEFAULT_AUTHENTICATION_CLASSES": [
    #     "rest_framework.authentication.SessionAuthentication",
    # ],
}

CSRF_FAILURE_VIEW = 'django.views.csrf.csrf_failure'

EVENTSTREAM_CHANNELS = {
    "fixture-updates": lambda request: True,
}


EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "10.10.10.34"
EMAIL_PORT = 25
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
EMAIL_USE_TLS = False
EMAIL_USE_SSL = False
DEFAULT_FROM_EMAIL = "Registrations@bitron.pl"
