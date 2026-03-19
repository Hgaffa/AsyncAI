asyncai.exceptions
==================

All asyncai-specific exceptions inherit from a common ``AsyncAIError`` base so
callers can catch the whole family with a single ``except AsyncAIError`` clause.

``WorkflowError``
   Raised by :func:`~asyncai.workflow.WorkflowHandle.result` when the workflow
   reaches ``FAILED`` status, and by :func:`~asyncai.gather.gather` when
   called outside a ``@workflow`` function or when any child job fails.

``UnknownTaskError``
   Raised by :class:`~asyncai.registry.TaskRegistry` when the worker encounters
   a job whose ``type`` has not been registered (i.e. the module containing the
   ``@task`` decorator was never imported by the worker process).

.. automodule:: asyncai.exceptions
   :members:
   :undoc-members:
   :show-inheritance:
