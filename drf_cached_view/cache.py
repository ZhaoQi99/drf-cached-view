import json

from django.apps import apps
from django.conf import settings
from rest_framework.settings import api_settings

from .settings import cache_view_settings


class BaseCache:
    @property
    def cache(self):
        """Get the Django cache interface.

        This allows disabling the cache with
        settings.USE_DRF_INSTANCE_CACHE=False.  It also delays import so that
        Django Debug Toolbar will record cache requests.
        """
        if not self._cache:
            use_cache = getattr(settings, "USE_DRF_INSTANCE_CACHE", True)
            if use_cache:
                from django.core.cache import cache

                self._cache = cache
        return self._cache

    def get_model(self, model_name):
        try:
            app_label, model_name = model_name.split(".", 1)
        except ValueError:
            app_label = None

        if app_label:
            return apps.get_model(app_label, model_name)

        models = list()
        for model in apps.get_models():
            if model._meta.model_name.lower() == model_name.lower():
                models.append(model)

        if len(models) > 1:
            raise LookupError("More than one models found with name '%s'." % model_name)
        elif len(models) == 0:
            raise LookupError("Model '%s' not found." % model_name)

        return models[0]

    def key_for(self, model_name, obj_pk):
        model = self.get_model(model_name)
        return self._key_for(model, obj_pk)

    def _key_for(self, model, obj_pk):
        return "{prefix}_{app_label}.{model_name}_{pk}".format(
            prefix=cache_view_settings.CACHE_KEY_PREFIX,
            app_label=model._meta.app_label,
            model_name=model._meta.model_name,
            pk=obj_pk,
        )

    def delete(self, model_name, obj_pk):
        key = self.key_for(model_name, obj_pk)
        self.cache.delete(key)

    def get_serializer(self, model_name):
        raise NotImplementedError

    def get_loader(self, model_name):
        raise NotImplementedError

    def get_invalidator(self, model_name):
        raise NotImplementedError

    def get_instances(self, object_specs):
        """
        Get objects from cache or database based on the given object specifications.

        Args:
            object_specs (list): A list of tuples containing the model name and object primary key.

        Returns:
            dict: A dictionary containing the fetched objects and their corresponding keys.

        """
        result = dict()
        spec_keys = set()
        cache_keys = []

        # Construct all the cache keys to fetch
        for model_name, obj_pk in object_specs:
            obj_key = self.key_for(model_name, obj_pk)
            spec_keys.add((model_name, obj_pk, obj_key))
            cache_keys.append(obj_key)

        cache_values = self.cache.get_many(cache_keys)

        cache_to_set = {}
        for model_name, obj_pk, obj_key in spec_keys:
            obj_native = cache_values.get(obj_key, None)

            # If the object is not in cache or invalid, load from database
            if obj_native is None:
                obj = self.get_loader(model_name)(obj_pk)
                serializer = self.get_serializer(model_name)
                obj_native = serializer(obj) if obj else None

                if obj:
                    cache_to_set[obj_key] = obj_native

            if obj_native:
                result[(model_name, obj_pk)] = (obj_native, obj_key, obj)

        if cache_to_set:
            self.cache.set_many(cache_to_set)

        return result

    def update_instance(self, model_name, pk, instance=None, update_only=False):
        """
        Create or update a cached instance.

        Args:
            model_name (str): The name of the model.
            pk (int): The primary key of the instance.
            instance (object, optional): The Django model instance, or None to load it.
            update_only (bool, optional): If False (default), then missing cache entries will be
                populated and will cause follow-on invalidation. If True, then only entries already
                in the cache will be updated and cause follow-on invalidation.

        Returns:
            list: A list of tuples (model name, pk, immediate) that also needs to be updated.
        """
        serializer = self.get_serializer(model_name)
        loader = self.get_loader(model_name)
        invalidator = self.get_invalidator(model_name)

        if serializer is None and loader is None and invalidator is None:
            return

        # Try to load the instance
        if not instance:
            instance = loader(pk)

        # Get current value, if in cache
        key = self.key_for(model_name, pk)
        current = self.cache.get(key, default=None)

        perform_operation = False

        if instance is None:
            if current:  # Clear cache
                perform_operation = True
                self.cache.delete(key)
        else:
            new = serializer(instance)
            if current != new:
                if not update_only or (update_only and current):
                    perform_operation = True
                    self.cache.set(key, json.dumps(new))

        invalid = list()
        if instance and perform_operation:
            for upstream in invalidator(instance):
                if isinstance(upstream, str):
                    self.cache.delete(upstream)
                else:
                    model_name, pk, immediate = upstream
                    if immediate:
                        key = self.key_for(model_name, pk)
                        self.cache.delete(key)
                    invalid.append((model_name, pk, immediate))

        return invalid


class ViewCache(BaseCache):
    def __init__(self, serializer=None, view=None):
        self.serializer_class = serializer
        self.view = view
        self.queryset = view.queryset
        super().__init__()

    def get_serializer(self, model_name):
        return lambda x: self.serializer_class(x).data

    def get_loader(self, model_name):
        return lambda x: self.queryset.model.objects.get(
            **{self.view.lookup_field: x},
        )

    def get_invalidator(self, model_name):
        return []
