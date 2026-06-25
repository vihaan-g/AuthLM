# General Project Rules

## Before coding
- Restate the task goal and relevant assumptions before writing code.
- Check whether the needed logic already exists before writing new code.

## Scope and style
- Follow DRY, KISS, and YAGNI. Prefer simple, direct solutions over clever ones.
- Write the minimum code that solves the task. Do not add speculative abstractions, future-proofing, or unrelated cleanup.
- Touch only files required by the task. Preserve existing style, naming, and structure unless the task explicitly asks to change them.
- Change one concern at a time. Do not reorganize, rename, or restructure unrelated code.

## Dependencies
- Do not add dependencies without explicit instruction. Prefer stdlib and existing project packages.
- Install dependencies only into project environments, never globally, and record them in project config files.
- Read installed dependency source code when behavior is uncertain. Do not guess APIs or method signatures.

## Functions and types
- Write pure functions where practical: return new values instead of mutating input parameters or global state.
- Keep functions single-purpose. Do not add flag parameters or multi-mode behavior that switches logic paths.
- Do not create single-use helper functions or trivial wrappers around builtins, stdlib calls, or one linear workflow.
- Use strict typing everywhere supported: function returns, variables, collections, and complex data structures.
- Avoid untyped variables, catch-all generic types, and vague data containers.
- Place imports at the top of the file unless the language or framework requires otherwise.

## Naming and module structure
- Organize code into coherent modules only when there is a clear domain boundary.
- Do not create junk-drawer files or packages named `utils`, `helpers`, `common`, `manager`, `service`, `processor`, or `coordinator`.
- Use domain-specific names such as `extract_phone_numbers` or `fetch_business_listings`; avoid names like `process_data`, `handle_request`, and `helper`.

## Abstractions and concurrency
- Do not add ABCs, factories, registries, dependency injection, controller/service/repository layers, or interfaces with only one implementation.
- Prefer duplication over an incorrect abstraction.
- Do not use `async` unless there is real concurrency. Sequential awaits are a bug.
- Watch for hidden O(n^2) behavior from membership checks, repeated I/O, or repeated conversions inside loops.

## Comments
- Use comments only for non-obvious intent, edge cases, or external constraints. Do not paraphrase the code.
- Write comments in English only. Prefer docstrings for code documentation over scattered inline explanations.

## Error handling
- Raise errors explicitly. Never silently ignore failures, return `None` on failure, or swallow exceptions.
- Use specific error types. Do not use catch-all handlers that hide root causes.
- Do not add fallbacks unless explicitly requested. Fix root causes, not symptoms.
- Error messages must include actionable context such as request parameters, response bodies, and status codes when relevant.
- For external API calls, retry only when the project already has a retry policy or the task asks for one; log or warn on retries, then raise the last error.

## Testing and verification
- Respect the existing test strategy. Do not add unit tests by default.
- Prefer integration or end-to-end tests that validate real behavior. Never add tests only to raise coverage numbers.
- Verify before declaring work complete. Run the most relevant compile, lint, typecheck, and test commands available for the files changed.

## Commits
- Do not use emojis in commit messages.
