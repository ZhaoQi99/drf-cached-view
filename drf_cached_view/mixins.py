from django.http import Http404
from rest_framework.generics import get_object_or_404

from .models import CachedQueryset


class BaseCachedViewMixin:
    """Mixin to add caching to a DRF viewset.

    A user should either define cache_class or override get_queryset_cache().
    """

    get_object_or_404 = get_object_or_404

    def get_queryset(self):
        """Get the queryset for the action.

        If action is read action, return a CachedQueryset
        Otherwise, return a Django queryset
        """
        queryset = super(BaseCachedViewMixin, self).get_queryset()
        if self.action in ("list", "retrieve"):
            return CachedQueryset(self.get_queryset_cache(), queryset=queryset)
        else:
            return queryset

    def get_queryset_cache(self):
        """Get the cache to use for querysets."""
        return self.cache_class()

    def get_object(self):
        """
        Return the object the view is displaying.

        Same as rest_framework.generics.GenericAPIView, but:
        - Failed assertions instead of deprecations
        """
        queryset = self.filter_queryset(self.get_queryset())

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        assert lookup_url_kwarg in self.kwargs, (
            "Expected view %s to be called with a URL keyword argument "
            'named "%s". Fix your URL conf, or set the `.lookup_field` '
            "attribute on the view correctly."
            % (self.__class__.__name__, lookup_url_kwarg)
        )

        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = self.get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj

    def get_object_or_404(self, queryset, *filter_args, **filter_kwargs):
        """Return an object or raise a 404.

        Same as Django's standard shortcut, but make sure to raise 404
        if the filter_kwargs don't match the required types.
        """
        if isinstance(queryset, CachedQueryset):
            try:
                return queryset.get(*filter_args, **filter_kwargs)
            except queryset.model.DoesNotExist:
                raise Http404("No %s matches the given query." % queryset.model)
        else:
            return get_object_or_404(queryset, *filter_args, **filter_kwargs)


class CachedViewMixin(BaseCachedViewMixin):
    def get_queryset_cache(self):
        return self.cache_class(serializer_class=self.get_serializer_class())
