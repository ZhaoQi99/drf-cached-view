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
        if name in self.__dict__:
            return self.__dict__[name]

        try:
            self._model._meta.get_field(name)
        except FieldDoesNotExist:
            if name in self._data:
                return self._data[name]
            elif name in ['pk',]:
                return getattr(self.obj, name)
            else:
                raise AttributeError(
                    "%r for %r has no attribute %r"
                    % (self.__class__, self._model._meta.object_name, name)
                )
        else:
            return getattr(self.obj, name)

    def __str__(self):
        return str(self.obj)

    def __repr__(self):
        return "<%s %r>" % (self.__class__.__name__, self.obj)


class CachedQueryset(models.QuerySet):
    """Emulate a Djange queryset, but with data loaded from the cache.

    A real queryset is used to get filtered lists of primary keys, but the
    cache is used instead of the database to get the instance data.
    """

    def __init__(self, cache, queryset, primary_keys=None):
        """Initialize a CachedQueryset."""
        self.cache = cache
        self.queryset = queryset
        self.model = queryset.model
        self._primary_keys = primary_keys

        super().__init__(self.model, queryset._query, queryset._db, queryset._hints)

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
            model_data = instances.get((model_name, pk), {})[0]
            yield CachedModel(self.model, model_data)

    def __len__(self):
        return self.count()

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
        return self.__class__(self.cache, queryset)

    def get(self, **kwargs):
        """Return the single item from the filtered queryset."""
        pk = self.queryset.get(**kwargs).pk
        model_name = self.model.__name__
        object_spec = (model_name, pk)
        instances = self.cache.get_instances((object_spec,))
        try:
            model_data = instances[(model_name, pk)][0]
        except KeyError:
            raise self.model.DoesNotExist(
                "No match for %r with kwargs %r" % (self.model, kwargs)
            )
        else:
            return CachedModel(self.model, model_data)

    def __getitem__(self, key):
        """Access the queryset by index or range."""
        if self._primary_keys is None:
            pks = self.queryset.values_list("pk", flat=True)[key]
        else:
            pks = self.pks[key]
            if isinstance(key, int):
                pks = [pks]
        return CachedQueryset(self.cache, self.queryset, pks)

    def order_by(self, *field_names):
        """Order the queryset."""
        queryset = self.queryset.order_by(*field_names)
        return self.__class__(self.cache, queryset)
