# Security Policy

## Supported Versions

AuthLM follows [Semantic Versioning 2.0.0](https://semver.org/). Security fixes are released for the latest minor line only.

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |
| < 0.1   | No        |

While AuthLM is at `0.y.z`, the public API is unstable. At `1.0.0`, security support expands to the latest minor of the previous major version as well.

## Reporting a Vulnerability

**Do not file public issues for security vulnerabilities.**

AuthLM uses GitHub's private vulnerability reporting. To disclose a vulnerability securely:

1. Go to the repository's **Security** tab.
2. Click **"Report a vulnerability"**.
3. Provide as much detail as possible: affected version, reproduction steps, impact assessment.

If you cannot use GitHub Security Advisories, email security@authlm.dev as a fallback disclosure channel.

**Response SLA:**

- Acknowledgement: within **72 hours** of report.
- Patch or mitigation: within **14 days** for critical issues, **30 days** for high/medium.

We follow coordinated disclosure. We will work with you on an embargo period and credit you in the release notes (unless you prefer to remain anonymous).

## Threat Model

### AuthLM protects against

- **Secrets written to disk in plaintext.** The default backend is the OS keychain (macOS Keychain, Windows Credential Manager, Linux Secret Service). Plaintext file storage is opt-in and warns.
- **Secrets appearing in log output or exception messages.** All logs route through a redaction layer in `authlm.connection_methods._oauth_helpers` (`redact_body`, `redact_url`, `_redact_dict`) that scrubs `Authorization` headers, OAuth tokens, API keys, and client secrets.
- **Secrets appearing in VCR cassettes.** Recorded HTTP fixtures are scrubbed via `filter_headers`, `filter_post_data_parameters`, and `before_record_response` hooks.
- **Token expiry going unnoticed.** The public `get_valid_credential()` API makes expiry explicit; consumers choose when to refresh rather than relying on silent auto-refresh on every read.
- **Refresh-token rotation bugs.** The centralized implementation persists both new access and refresh tokens atomically on every refresh, preventing the common "kept the old refresh token" failure mode.

### AuthLM does NOT protect against

- **A compromised host or root access.** The OS keychain is only as secure as the OS. An attacker with root on your machine can read the keychain.
- **In-process exfiltration by a malicious library.** AuthLM hands the secret to your code; what happens after that handoff is on you.
- **Malicious provider SDKs.** A backdoored `openai` package can exfiltrate the key after AuthLM retrieves it. AuthLM is a credential *source*, not a credential *destination*.
- **Network interception of API calls.** AuthLM uses `httpx` with HTTPS by default; if you downgrade to HTTP, that protection is lost.
- **Social engineering or phishing.** The user is the attack surface.

## Credential Storage Backends

| Backend | Security notes |
|---------|----------------|
| `KeyringStore` (default) | OS-protected. On macOS, requires user approval on first access. On Linux, requires a Secret Service backend (gnome-keyring, KWallet). |
| `EncryptedFileStore` | Fernet (AES-128-CBC + HMAC-SHA256) with PBKDF2-HMAC key derivation from a passphrase. Security is bounded by passphrase strength. On POSIX the file is `chmod 0o600`; on Windows the file is created with a Read+Write DACL for the current user only (inherited ACLs stripped) via `pywin32`. |
| `EnvStore` | Read-only. Reads from `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. Inherits the security of the environment: leaks to subprocesses, `ps` output, and crash dumps are possible. |
| `MemoryStore` | In-process only. Cleared on exit. Intended for tests, not production. |

## Logging and Redaction

All log output, exception messages, and VCR cassettes are processed by a redaction layer. The following are always redacted:

- `Authorization` headers (any scheme)
- `access_token`, `refresh_token`, `id_token` fields in JSON
- `api_key`, `secret`, `client_secret` fields in JSON
- Query parameters named `code`, `token`

`state` (the OAuth CSRF token) is intentionally NOT redacted: it is not a credential, redacting it would make OAuth flow debugging harder, and libraries like `authlib` similarly leave it unredacted. Logging `state=...` from authorize URLs and from loopback callbacks is safe and useful for diagnosing flow errors.

Library code uses the `logging` module at `DEBUG` level. There are **no `print()` calls** in library code. Secrets are never passed through `str()` or `repr()` in error messages.
- Pydantic credential models use `Field(repr=False)` on all secret fields (`ApiKeyCredential.secret`, `OAuthCredential.access_token`, `OAuthCredential.refresh_token`) so that `repr(cred)`, `print(cred)`, and debugger inspection do not leak secrets.

## Coordinated Disclosure

We follow a **90-day coordinated disclosure** policy. After 90 days from the initial report (or once a patch is released, whichever comes first), public disclosure is expected.

We will:

- Acknowledge your report within 72 hours.
- Provide a fix timeline within 14 days for critical issues.
- Credit you in the release notes (unless you prefer anonymity).
- Coordinate the public disclosure date with you.

We will not pursue legal action against security researchers who act in good faith, comply with this policy, and avoid privacy violations, service disruption, and destruction of data.

## Security-Relevant Dependencies

AuthLM's security depends on the integrity of its dependencies. All dependencies are:

- **Pinned in `uv.lock`** for reproducible installs.
- **Tracked by Dependabot** for security advisories (`uv` and `github-actions` ecosystems, weekly).
- **Scanned by `pip-audit`** in CI on every pull request.
- **Scanned by CodeQL** weekly and on every push to `main`.

If you discover a vulnerability in a dependency that affects AuthLM, please report it via the same private vulnerability channel.
