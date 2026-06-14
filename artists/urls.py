from django.urls import path

from .views import (
    ArtistCreateView,
    ArtistDeleteView,
    ArtistListView,
    ArtistRecordCreateView,
    ArtistRecordDeleteView,
    ArtistRecordListView,
    ArtistRecordUpdateView,
    ArtistUpdateView,
    GroupingCreateView,
    artist_bulk_upload_view,
    calcular_costes_por_tramo,
)

app_name = "artists"

urlpatterns = [
    path("", ArtistListView.as_view(), name="list"),
    path("registros/", ArtistRecordListView.as_view(), name="record-list"),
    path("api/calcular-costes/", calcular_costes_por_tramo, name="calcular-costes"),
    path("agrupaciones/nueva/", GroupingCreateView.as_view(), name="grouping-create"),
    path("new/", ArtistCreateView.as_view(), name="create"),
    path("bulk-upload/", artist_bulk_upload_view, name="bulk-upload"),
    path("registros/new/", ArtistRecordCreateView.as_view(), name="record-create"),
    path("registros/<int:pk>/edit/", ArtistRecordUpdateView.as_view(), name="record-update"),
    path("registros/<int:pk>/delete/", ArtistRecordDeleteView.as_view(), name="record-delete"),
    path("<int:pk>/edit/", ArtistUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", ArtistDeleteView.as_view(), name="delete"),
]
