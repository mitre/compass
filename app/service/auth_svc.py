"""Stub auth_svc for testing without the full Caldera framework."""


def for_all_public_methods(_decorator):
    """Identity class-decorator stub."""
    def wrapper(cls):
        return cls
    return wrapper


def check_authorization(func):
    return func
