"""Runtime-layer exceptions.

Separate from both the domain hierarchy (rule violations) and the
repository hierarchy (persistence failures): a runtime failure is an
orchestration concern.
"""


class RuntimeKernelError(Exception):
    """Base class for every runtime-layer error."""


class KernelLifecycleError(RuntimeKernelError):
    """An operation was attempted in a kernel state that does not permit it,
    or an invalid kernel lifecycle transition was requested."""


class BootError(RuntimeKernelError):
    """The boot sequence failed (load, structural integrity, or invariant
    validation). The kernel transitions to Failed and holds no state."""


class RuntimeInvariantError(RuntimeKernelError):
    """A runtime-enforced invariant does not hold — including the runtime
    invariant "exactly one Execution Context" and the Domain Invariants the
    Runtime Kernel enforces (BUSINESS_RULES.md)."""


class ServiceRegistryError(RuntimeKernelError):
    """Duplicate registration or lookup of an unknown runtime service."""
