# Generated by Django 2.1.4 on 2019-01-13 03:07

import django.db.models.deletion
from django.db import migrations, models

import django_pgschemas.schema
import django_pgschemas.utils


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Domain",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("domain", models.CharField(db_index=True, max_length=253)),
                ("folder", models.SlugField(blank=True, max_length=253)),
                ("is_primary", models.BooleanField(default=True)),
            ],
            options={"abstract": False},
        ),
        migrations.CreateModel(
            name="Catalog",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                )
            ],
        ),
        migrations.CreateModel(
            name="Tenant",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "schema_name",
                    models.CharField(
                        max_length=63,
                        unique=True,
                        validators=[django_pgschemas.utils.check_schema_name],
                    ),
                ),
            ],
            options={"abstract": False},
            bases=(django_pgschemas.schema.Schema, models.Model),
        ),
        migrations.AddField(
            model_name="domain",
            name="tenant",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="domains",
                to="shared_public.Tenant",
            ),
        ),
        migrations.AlterUniqueTogether(name="domain", unique_together={("domain", "folder")}),
    ]
