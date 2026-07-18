---
name: python-conventions
description: Mandatory conventions for every Python task. Always load before reading, reasoning about, reviewing, planning, generating, debugging, testing, refactoring, or editing any Python code or Python project. Covers style, typing, architecture, exceptions, filesystem, tooling, packaging, and project conventions.
---

# Python Conventions

Apply these rules for Python changes in this project.

## Rules

### Exceptions
- Use explicit checks before exceptions-as-control-flow. Prefer `if key in mapping` over catching `KeyError` for normal branching.
- Never use bare `except:` or `except Exception: pass`. Let unexpected failures surface.

### Typing
- Annotate all function signatures (parameters and return types) and module-level variables with type hints. Use `from __future__ import annotations` at the top of every file to enable deferred evaluation.
- Do not rely on type inference alone at the module level — annotate explicitly.
- Use `Self` return type on class methods returning `self`, and `type[Self]` on `__init_subclass__` / alternative constructors.
- Prefer `collections.abc` over `typing` for generic types (e.g., `collections.abc.Sequence` instead of `typing.Sequence`).
- Assert before `typing.cast()` unless the code is a measured hot path.
- Use `Literal` types for fixed string sets instead of plain `str`.

### Arguments
- Use keyword-only arguments for functions with five or more parameters.
- Do not add default parameter values. Make caller intent explicit.

### Object behavior and imports
- Magic methods such as `__len__`, `__bool__`, and `__contains__` must be O(1).
- Avoid import-time computation and side effects. Lazily compute expensive or environment-dependent values, using `functools.cache` when appropriate.

### Filesystem
- Check `Path.exists()` before `Path.resolve()` or `Path.is_relative_to()` when the path may not exist.

### Variable scope
- Declare variables close to their first use.

### Tooling and data boundaries
- Use strict static typing with `mypy --strict` or strict `pyright` when available.
- Use Ruff for linting and formatting when available.
- Use Pydantic models for data crossing process, network, config, or serialization boundaries.

## Common Mistakes
- Do not return `None` silently on failure.
- Do not hide filesystem errors behind broad exception handlers.
- Do not add `async` for sequential code without actual concurrency.
