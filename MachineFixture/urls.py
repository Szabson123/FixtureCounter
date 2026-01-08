from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


urlpatterns = [
    path('api/admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    path('', include('base.urls')),
    path('map/', include('map.urls')),
    path('api/golden-samples/', include('goldensample.urls')),
    path('api/process/', include('checkprocess.urls')),
    # path('user/', include('user_auth.urls')),
]