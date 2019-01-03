# django-pgschemas

[![Packaging: poetry](https://img.shields.io/badge/packaging-poetry-purple.svg)](https://github.com/sdispater/poetry)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

## Schemas

This app uses PostgreSQL schemas to support data multi-tenancy in a single Django project. For an accurate description on schemas, see [the official documentation](https://www.postgresql.org/docs/9.1/ddl-schemas.html).

The terms _schema_ and _tenant_ are used indistinctly all over the documentation. However, it is important to note some subtle differences between the two. We consider a _tenant_ to be a subset of data that can be accessed with a URL (routed), and we use database _schemas_ for that purpose. Still, there can be schemas that shouldn't be considered tenants according to our definition. One good example is the `public` schema, which contains data shared across all tenants. That said, remember that every tenant is a schema, but not every schema is a tenant.

## Usage

Use `django_pgschemas.postgresql_backend` as your database engine.

```python
DATABASES = {
    "default": {
        "ENGINE": "django_pgschemas.postgresql_backend",
        # ...
    }
}
```

Add the middleware `django_pgschemas.middleware.TenantMiddleware` to the top of `MIDDLEWARE`, so that each request can be set to use the correct schema.

```python
MIDDLEWARE = (
    "django_pgschemas.middleware.TenantMainMiddleware",
    #...
)
```

Add `django_pgschemas.routers.SyncRouter` to your `DATABASE_ROUTERS`, so that the correct apps can be synced, depending on the target schema.

```python
DATABASE_ROUTERS = (
    "django_pgschemas.routers.SyncRouter",
    #...
)
```

Add the minimal tenant configuration.

```python
TENANTS = {
    "public": {
        "APPS": [
            "django.contrib.contenttypes",
            "django.contrib.staticfiles",
            # ...
            "django_pgschemas",
            "shared_app",
            # ...
        ],
        "TENANT_MODEL": "shared_app.Client",
        "DOMAIN_MODEL": "shared_app.Domain",
    },
    # ...
    "default": {
        "APPS": [
            "django.contrib.auth",
            "django.contrib.sessions",
            # ...
            "tenant_app",
            # ...
        ],
        "URLCONF": "tenant_app.urls",
    }
}
```

Each entry in the `TENANTS` dictionary represents a static tenant, except for `default`, which controls the settings for dynamic tenants (that is, database controlled). `public` is always treated as shared schema and cannot be routed directly.

More static tenants can be added and routed.

```python
TENANTS = {
    # ...
    "www": {
        "APPS": [
            "django.contrib.auth",
            "django.contrib.sessions",
            # ...
            "main_app",
        ],
        "DOMAINS": ["mydomain.com"],
        "URLCONF": "main_app.urls",
    },
    "blog": {
        "APPS": [
            "django.contrib.auth",
            "django.contrib.sessions",
            # ...
            "blog_app",
        ],
        "DOMAINS": ["blog.mydomain.com", "help.mydomain.com"],
        "URLCONF": "blog_app.urls",
    },
    # ...
}
```

For Django to function properly, `INSTALLED_APPS` and `ROOT_URLCONF` settings must be defined. Just make them get their information from the `TENANTS` dictionary, for the sake of consistency.

```python
INSTALLED_APPS = []
for schema in TENANTS:
    INSTALLED_APPS += [app for app in TENANTS[schema]["APPS"] if app not in INSTALLED_APPS]

ROOT_URLCONF = TENANTS["default"]["URLCONF"]
```

Dynamic tenants need to be created through instances of `TENANTS["public"]["TENANT_MODEL"]`.

```python
# shared_app/models.py

from django.db import models
from django_pgschemas.models import TenantMixin, DomainMixin

class Client(TenantMixin):
    name = models.CharField(max_length=100)
    paid_until =  models.DateField(blank=True, null=True)
    on_trial = models.BooleanField(default=True)
    created_on = models.DateField(auto_now_add=True)

class Domain(DomainMixin):
    pass
```

Sync the public schema, in order to get `Client` model created. Also sync static schemas either one by one or using the `:static:` wildcard.

```bash
python manage.py migrate_schemas -s public
python manage.py migrate_schemas -s :static:
```

Create the first dynamic tenant.

```bash
>>> from shared_app.models import Client, Domain
>>> client1 = Client.objects.create(schema_name="client1")
>>> Domain.objects.create(domain="client1.mydomain.com", tenant=client1, is_primary=True)
```

Now any request made to `client1.mydomain.com` will automatically set PostgreSQL's `search_path` to `client1` and `public`, making shared apps available too. Also, any request to `blog.mydomain.com` or `help.mydomain.com` will set `search_path` to `blog` and `public`. This means that any call to the methods `filter`, `get`, `save`, `delete` or any other function involving a database connection will now be done at the correct schema, be it static or dynamic.

## Management commands

Management commands provided by Django or any 3rd party app will run by default on the `public` schema. To run a command on a specific tenant, you can use the provided command `runschema`.

```bash
python manage.py runschema shell -s tenant1
python manage.py runschema loaddata tenant_app.Products -s :dynamic:
```

We provide a custom `migrate_schemas` command (also aliased as `migrate`) that is capable of running migrations on specific schemas.

```bash
# all schemas
python manage.py migrate

# static schemas only
python manage.py migrate -s :static:

# dynamic schemas only
python manage.py migrate -s :dynamic:

# specific schema by exact schema name
python manage.py migrate -s tenant1

# specific schema by partially matched domain (startswith)
python manage.py migrate -s help.mydomain
```

## Gotchas

1. It is enforced that `django.contrib.contenttypes` should live in the `public` schema. This is to guarantee that content types from all apps/tenants are stored in a single place.

2. It is enforced that `django.contrib.sessions` can only live in schemas where the app that defines the user model also lives. The user app is `django.contrib.auth` by default, but could be changed via `AUTH_USER_MODEL` setting. This is to guarantee that session information is not leaked across tenants that do not share the same user base.

## Credits

This project stands on the shoulders of giants.

- Tom Turner with `django-tenants`.
- Bernardo Pires with `django-tenant-schemas`.
- Vlada Macek with `django-schemata`.
