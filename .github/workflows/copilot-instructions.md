## Python Documentation, Typing & Comment Standards

All newly added or modified Python code MUST follow these rules. When editing existing code that does not meet them, opportunistically improve it (boy-scout rule) without large refactors.

### 1. Docstrings (Required Everywhere)
Provide a triple-quoted docstring for:
1. Public modules (top of file) – state purpose, key responsibilities, important side-effects or external services.
2. Public classes – what the class represents, invariants, thread-/async-safety, lifecycle expectations.
3. Public functions & methods (including FastAPI route handlers, async functions, background tasks) – concise summary first line (imperative mood), then detailed description if needed.

Follow Google-style sections (preferred) or NumPy-style if matching surrounding code. Maintain consistency within a file. Example (Google style):

```python
def fetch_user_profile(user_id: str, *, include_permissions: bool = False) -> UserProfile:
	"""Fetch a user profile from Firestore.

	Performs a single point lookup. Falls back to cache if available. Raises a typed error instead of returning None.

	Args:
		user_id: Stable external user identifier.
		include_permissions: If True, also loads permission scopes.

	Returns:
		Fully populated UserProfile domain object.

	Raises:
		UserNotFoundError: If the user cannot be found.
		PermissionServiceError: If permission enrichment fails.
	"""
	...
```

Docstring content rules:
- First line: <= 80 chars summary.
- Omit parameter descriptions ONLY if the meaning is 100% obvious AND adding text is noise.
- Use precise domain terminology; avoid vague words like "thing", "data".
- For async functions: mention concurrency constraints if any.
- For generators / iterators: document yield semantics using a Yields: section.
- For context managers: document enter/exit side-effects.

### 2. Typing (Mypy-Friendly)
Type annotate ALL new function/method signatures (parameters + return). No implicit Any unless unavoidable (e.g., 3rd-party dynamic objects). Prefer:
- Builtins over typing aliases when possible (list[str] not List[str] – Python 3.12+).
- `from __future__ import annotations` (add if missing at top of file before other code) for forward refs & performance.
- `typing` helpers: Protocol, TypedDict, Literal, Annotated, NewType where they clarify meaning.
- Narrow types: Sequence, Mapping, Iterable for read-only views instead of concrete list/dict when mutation not required.
- Use `| None` (PEP 604) instead of Optional[T] unless consistency requires otherwise.
- Avoid cast() unless last resort; prefer refining logic.
- Return `None` explicitly typed when function produces side-effects only.
- Use `NoReturn` for functions that always raise or exit.
- Keep mypy happy: eliminate unreachable branches, avoid needless `# type: ignore`.

When ignoring a type error is unavoidable, use: `# type: ignore[error-code]  # explanation` – never bare ignores. Remove ignores once no longer needed.

### 3. Inline Comments & Structure
- Prefer clear naming over comments; comments justify non-obvious decisions.
- Place explanatory comments ABOVE the line they clarify.
- Use TODO with owner + context + tracking reference: `# TODO(avosseler, 2025-09): Replace polling with pub/sub (JIRA-123).`
- Avoid narrating the code ("increment i"). Explain WHY, constraints, invariants, performance choices, external API quirks.
- For complex conditionals, add a brief decision explanation.
- Keep comment width <= 110 chars (aligns with Ruff line-length exemption for code at 120).

### 4. FastAPI & Pydantic Specifics
- Always type request/response models explicitly with Pydantic models (or TypedDict for internal layer boundaries).
- Route handlers must declare response model or return a typed domain object converted explicitly.
- Background tasks & dependencies also need docstrings when logic > trivial.

### 5. Exceptions
- Raise domain-specific exceptions (create them if missing) instead of returning sentinel values.
- Document all intentionally raised exceptions in the docstring Raises: section.
- Do not catch broad Exception unless adding context then re-raising.

### 6. Example Pattern (Combined)

```python
from __future__ import annotations
from typing import Sequence, Literal

class UserNotFoundError(RuntimeError):
	"""Raised when a user lookup fails after all retry / fallback strategies."""

def select_primary_email(emails: Sequence[str], strategy: Literal["first", "longest"] = "first") -> str:
	"""Select the primary email from a non-empty sequence.

	Args:
		emails: One or more validated, normalized email strings.
		strategy: Selection heuristic; "first" preserves input order; "longest" picks the longest local-part.

	Returns:
		Chosen email string.

	Raises:
		ValueError: If emails is empty or strategy unsupported.
	"""
	if not emails:
		raise ValueError("emails must be non-empty")
	if strategy == "first":
		return emails[0]
	if strategy == "longest":
		return max(emails, key=lambda e: e.split("@", 1)[0].__len__())
	raise ValueError(f"Unsupported strategy: {strategy}")
```

### 7. Refactoring Legacy Code
When touching legacy untyped or undocumented code:
- Add at least function-level docstring & full typing for changed functions.
- Split overly long functions (>60 lines) only if safe; otherwise document rationale & TODO for later extraction.
- Replace broad except with targeted ones and document remaining broad usage.

### 8. Verification
- Run `ruff check` and `ruff format` before commit (or rely on pre-commit if configured).
- Run `mypy` for changed files; fix or justify minimal ignores.

### 9. Prohibited Patterns
- Bare `except:` blocks.
- Silent pass on exceptions (log + re-raise or handle intentionally).
- Returning mixed shaped dict vs. defined model.
- Adding new untyped global mutable state.

### 10. Quick Checklist Before PR
- [ ] Module/class/function docstrings present & meaningful
- [ ] Full type coverage (parameters & return)
- [ ] No stray Any introduced
- [ ] Inline comments explain intent, not mechanics
- [ ] Exceptions documented
- [ ] No new bare ignores
- [ ] mypy & ruff clean locally

Adhering to these ensures maintainability, safety under refactors, and higher-quality AI assistance.

