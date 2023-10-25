from rest_framework.viewsets import ModelViewSet as DRFModelViewSet
from rest_framework.viewsets import ReadOnlyModelViewSet as DRFReadOnlyModelViewSet
from drf_cached_view.cache import ViewCache
from drf_cached_view.mixins import CachedViewMixin


class ModelViewSet(CachedViewMixin, DRFModelViewSet):
    cache_class = ViewCache


class ReadOnlyModelViewSet(CachedViewMixin, DRFReadOnlyModelViewSet):
    cache_class = ViewCache
