# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| latest (main) | ✅ |
| older releases | ❌ |

Only the latest release on the `main` branch receives security fixes. Please update before reporting.

## Scope

EmailFilter is a self-hosted, containerized API service. The following are considered in-scope for security reports:

- Remote code execution or command injection via API endpoints
- SSRF (Server-Side Request Forgery) through email/domain input
- DNS rebinding or MX lookup abuse leading to internal network access
- Container escape or privilege escalation
- Information disclosure of internal network topology via error messages
- Blacklist/whitelist bypass via input manipulation
- Denial of service via crafted input (e.g. infinite DNS loops, slowloris)

Out of scope:

- Issues requiring physical access to the host
- Security of third-party dependencies unrelated to EmailFilter's functionality
- Rate limiting (caller's responsibility to implement)
- Issues on unofficial forks or modified deployments

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security issues by emailing:

**stefan@pejcic.rs**

Include in your report:

- Description of the vulnerability
- Steps to reproduce (curl commands, payloads, config)
- Impact assessment
- Your suggested fix (optional but appreciated)

You can expect an acknowledgment within **48 hours** and a status update within **7 days**.

## Deployment Hardening

If you run EmailFilter in production, consider the following:

**Network exposure**

EmailFilter binds to `localhost:8000` by default. Do not expose it publicly without authentication in front of it (nginx auth_basic, firewall rules, or VPN).

```nginx
# Example: restrict to internal IPs only
location /filter-email {
    allow 10.0.0.0/8;
    allow 192.168.0.0/16;
    deny all;
    proxy_pass http://localhost:8000;
}
```

**Docker network isolation**

Run EmailFilter in an isolated Docker network and only allow access from trusted services:

```yaml
networks:
  internal:
    internal: true
```

**Input validation**

EmailFilter performs DNS and SMTP outbound lookups based on user-supplied input. Restrict who can call the API to trusted internal services only.

**Rate limiting**

Add rate limiting at the reverse proxy level to prevent abuse:

```nginx
limit_req_zone $binary_remote_addr zone=emailfilter:10m rate=10r/s;
limit_req zone=emailfilter burst=20 nodelay;
```

**Container user**

Ensure the container does not run as root. Verify with:

```bash
docker exec emailfilter whoami
```

## Disclosure Policy

- Security issues will be fixed in a patch release as soon as possible.
- A GitHub Security Advisory will be published after the fix is released.
- Credit will be given to the reporter unless they prefer to remain anonymous.
