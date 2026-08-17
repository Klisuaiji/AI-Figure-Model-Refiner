import functools
import traceback


class AFRError(Exception):
    """Base error for the AI Figure Refiner plugin."""


class DiagnosticError(AFRError):
    pass


class RepairError(AFRError):
    pass


class ExportError(AFRError):
    pass


class DependencyError(AFRError):
    """Raised when an optional dependency (e.g. onnxruntime) is missing."""


def safe_run(logger=None):
    """Decorator: catches exceptions, logs them, returns None instead of
    raising. Keeps Blender's UI responsive even when a task fails."""

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **k):
            try:
                return fn(*a, **k)
            except Exception as e:
                if logger is not None:
                    logger.error("%s failed: %s" % (getattr(fn, "__name__", "task"), e))
                traceback.print_exc()
                return None

        return wrapper

    return deco