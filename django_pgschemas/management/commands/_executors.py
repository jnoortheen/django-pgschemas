import functools
import multiprocessing
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError, OutputWrapper
from django.db import connection, connections, transaction

from django_pgschemas.routing.info import DomainInfo
from django_pgschemas.schema import Schema, activate
from django_pgschemas.utils import get_clone_reference, get_tenant_model

HAS_TQDM = False

try:
    from tqdm import tqdm

    HAS_TQDM = True
except ImportError:
    pass

def run_on_schema(
    schema_name,
    executor_codename,
    command,
    function_name=None,
    args=None,
    kwargs=None,
    pass_schema_in_kwargs=False,
    fork_db=False,
):
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}

    if not isinstance(command, BaseCommand):
        # Parallel executor needs to pass command 'type' instead of 'instance'
        # Therefore, no customizations for the command can be done, nor using custom stdout, stderr
        command = command()

    command.stdout = kwargs.pop("stdout", command.stdout)
    if not isinstance(command.stdout, OutputWrapper):
        command.stdout = OutputWrapper(command.stdout)

    command.stderr = kwargs.pop("stderr", command.stderr)
    if not isinstance(command.stderr, OutputWrapper):
        command.stderr = OutputWrapper(command.stderr)

    # Since we are prepending every output with the schema_name and executor, we need to determine
    # whether we need to do so based on the last ending used to write. If the last write didn't end
    # in '\n' then we don't do the prefixing in order to keep the output looking good.
    class StyleFunc:
        last_message = None

        def __call__(self, message):
            last_message = self.last_message
            self.last_message = message
            if last_message is None or last_message.endswith("\n"):
                return "[%s:%s] %s" % (
                    command.style.NOTICE(executor_codename),
                    command.style.NOTICE(schema_name),
                    message,
                )
            return message

    command.stdout.style_func = StyleFunc()
    command.stderr.style_func = StyleFunc()

    if fork_db:
        connections.close_all()

    if schema_name in settings.TENANTS:
        domains = settings.TENANTS[schema_name].get("DOMAINS", [])
        schema = Schema.create(
            schema_name=schema_name,
            routing=DomainInfo(domain=domains[0] if domains else None),
        )
    elif schema_name == get_clone_reference():
        schema = Schema.create(schema_name=schema_name)
    elif (TenantModel := get_tenant_model()) is not None:
        schema = TenantModel.objects.get(schema_name=schema_name)
    else:
        raise CommandError(f"Unable to find schema {schema_name}!")

    activate(schema)

    if pass_schema_in_kwargs:
        kwargs.update({"schema_name": schema_name})

    if function_name == "special:call_command":
        call_command(command, *args, **kwargs)
    elif function_name == "special:run_from_argv":
        command.run_from_argv(args)
    else:
        getattr(command, function_name)(*args, **kwargs)

    if fork_db:
        transaction.commit()
        connection.close()

    return schema_name


def sequential(
    schemas, command, function_name, args=None, kwargs=None, pass_schema_in_kwargs=False
):
    runner = functools.partial(
        run_on_schema,
        executor_codename="sequential",
        command=command,
        function_name=function_name,
        args=args,
        kwargs=kwargs,
        pass_schema_in_kwargs=pass_schema_in_kwargs,
        fork_db=False,
    )
    if HAS_TQDM:
        for schema in tqdm(schemas, desc="Migrating schemas"):
            runner(schema)
    else:
        for schema in schemas:
            runner(schema)
    return schemas


def init_configurations():
    """Initialize django-configurations"""
    try:
        from configurations import setup
        setup()
    except ImportError:
        pass

def parallel(schemas, command, function_name, args=None, kwargs=None, pass_schema_in_kwargs=False):
    processes = getattr(settings, "PGSCHEMAS_PARALLEL_MAX_PROCESSES", None)
    pool = multiprocessing.Pool(processes=processes, initializer=init_configurations)
    runner = functools.partial(
        run_on_schema,
        executor_codename="parallel",
        command=type(command),  # Can't pass streams to children processes
        function_name=function_name,
        args=args,
        kwargs=kwargs,
        pass_schema_in_kwargs=pass_schema_in_kwargs,
        fork_db=True,
    )

    if HAS_TQDM:
        return list(tqdm(pool.imap(runner, schemas), desc="Migrating schemas", total=len(schemas)))
    return pool.map(runner, schemas)
