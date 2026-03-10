class AsyncAIError(Exception):
    pass


class UnknownTaskError(AsyncAIError):
    pass


class WorkflowError(AsyncAIError):
    pass
