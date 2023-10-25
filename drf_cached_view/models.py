from django.core.exceptions import FieldDoesNotExist
from django.db import models


class CachedModel:
    """Emulate a Django model, but with data loaded from the cache."""

    def __init__(self, model, data):
        """Initialize a CachedModel."""
        self._model = model
        self._data = data
        self._obj = None

    @property
    def obj(self):
        if self._obj is None:
            self._obj = self.get_obj()
        return self._obj

    def get_obj(self):
        kwargs = dict()
        for name, value in self._data.items():
            try:
                field = self._model._meta.get_field(name)
            except FieldDoesNotExist:
                pass
            else:
                if isinstance(field, models.ForeignKey):
                    kwargs[f"{name}_id"] = value
                else:
                    kwargs[name] = value

        return self._model(**kwargs)

    def __getattr__(self, name):
        """Return an attribute from the cached data."""
        try:
            value = getattr(self.obj, name)
        except AttributeError:
            if name in self._data:
                return self._data[name]
            else:
                raise AttributeError(
                    "%r for %r has no attribute %r"
                    % (self.__class__, self._model._meta.object_name, name)
                )
        else:
            return value


class CachedQueryset:
    """Emulate a Djange queryset, but with data loaded from the cache.

    A real queryset is used to get filtered lists of primary keys, but the
    cache is used instead of the database to get the instance data.
    """

    def __init__(self, cache, queryset, primary_keys=None):
        """Initialize a CachedQueryset."""
        self.cache = cache
        self.queryset = queryset
        self.model = queryset.model
        self.filter_kwargs = {}
        self._primary_keys = primary_keys

    @property
    def pks(self):
        """Lazy-load the primary keys."""
        if self._primary_keys is None:
            self._primary_keys = list(self.queryset.values_list("pk", flat=True))
        return self._primary_keys

    def __iter__(self):
        """Return the cached data as a list."""
        model_name = self.model.__name__
        object_specs = [(model_name, pk) for pk in self.pks]
        instances = self.cache.get_instances(object_specs)
        for pk in self.pks:
            model_data = instances.get((model_name, pk), {})
            yield CachedModel(self.model, model_data)

    def all(self):
        """Handle asking for an unfiltered queryset."""
        return self

    def none(self):
        """Handle asking for an empty queryset."""
        return CachedQueryset(self.cache, self.queryset.none(), [])

    def count(self):
        """Return a count of instances."""
        if self._primary_keys is None:
            return self.queryset.count()
        else:
            return len(self.pks)

    def filter(self, **kwargs):
        """Filter the base queryset."""
        queryset = self.queryset.filter(**kwargs)
        return self.__class__(self.cache, queryset, self._primary_keys)

    def get(self, **kwargs):
        """Return the single item from the filtered queryset."""
        pk = self.queryset.get(**kwargs).pk
        model_name = self.model.__name__
        object_spec = (model_name, pk)
        instances = self.cache.get_instances((object_spec,))
        try:
            model_data = instances[(model_name, pk)]
        except KeyError:
            raise self.model.DoesNotExist(
                "No match for %r with args %r, kwargs %r" % (self.model, args, kwargs)
            )
        else:
            return CachedModel(self.model, model_data)

    def __getitem__(self, key):
        """Access the queryset by index or range."""
        if self._primary_keys is None:
            pks = self.queryset.values_list("pk", flat=True)[key]
        else:
            pks = self.pks[key]
        return CachedQueryset(self.cache, self.queryset, pks)

    def order_by(self, *field_names):
        """Order the queryset."""
        queryset = self.queryset.order_by(*field_names)
        return self.__class__(self.cache, queryset, [])
