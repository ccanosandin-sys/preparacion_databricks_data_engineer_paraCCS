from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(url="/landing", permanent=False)),
    path("", include("tier_view.urls")),
]
