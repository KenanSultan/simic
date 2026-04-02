from django.urls import path

from review import views

app_name = "review"

urlpatterns = [
    path("", views.market_redirect, name="index"),
    path("<str:market>/", views.dashboard, name="dashboard"),
    path("<str:market>/golden/", views.golden_list, name="golden-list"),
    path("<str:market>/golden/<str:match_group_id>/", views.golden_detail, name="golden-detail"),
    path("<str:market>/images/", views.image_gallery, name="image-gallery"),
    path("<str:market>/warnings/", views.warnings, name="warnings"),
    path("<str:market>/singles/", views.singles, name="singles"),
    path("<str:market>/similar/", views.similar, name="similar"),
]
