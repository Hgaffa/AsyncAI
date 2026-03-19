asyncai.registry
================

:class:`~asyncai.registry.TaskRegistry` is a process-level singleton that maps
task names to their callable implementations. It is populated automatically when
modules containing ``@task`` or ``@workflow`` decorators are imported.

The worker looks up the correct function by ``job.type`` (the registered name)
before executing each job. If the worker process has not imported the module that
defines a given task, the lookup raises
:exc:`~asyncai.exceptions.UnknownTaskError`.

.. automodule:: asyncai.registry
   :members:
   :undoc-members:
   :show-inheritance:
