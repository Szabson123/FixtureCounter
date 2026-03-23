from django.urls import path
from .views import *


urlpatterns = [
    path('unlinking/<int:user_card_id>/', ProcessUnlinkingListView.as_view(), name='unlig-statues'),
    path('unlinking/login/<int:user_card_id>/', LoginProfileUnlkiner.as_view(), name='unlig-statues'),
    path('unlinking/create-profile/', CreateUserLinkingProfile.as_view(), name='create-profile'),
]
