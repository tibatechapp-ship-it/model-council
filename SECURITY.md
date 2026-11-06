# Security Policy

## Reporting a Vulnerability

Please do not disclose exploitable vulnerabilities in public issues.

Report security concerns privately through the GitHub repository security advisory feature.

## Security Principles

- Provider API keys must remain confidential.
- Secrets must never appear in logs or model-to-model messages.
- Model outputs are untrusted data.
- Model-generated commands must never execute automatically.
- Static analysis must remain read-only by default.
- External provider requests must respect timeouts and budget limits.

## Scope

Security reports concerning authentication, authorization, credential handling, data exposure, unsafe execution, and API vulnerabilities are welcome.
