from rest_framework.viewsets import ModelViewSet as DRFModelViewSet
from rest_framework.viewsets import ReadOnlyModelViewSet as DRFReadOnlyModelViewSet

from drf_cached_view.mixins import CachedViewMixin


class ModelViewSet(CachedViewMixin, DRFModelViewSet):
    pass


class ReadOnlyModelViewSet(CachedViewMixin, DRFReadOnlyModelViewSet):
    pass
