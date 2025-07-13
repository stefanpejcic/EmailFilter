# emailfilter 📨🔐
Self-hosted, privacy-focused email verification

emailfilter is a lightweight, self-hosted containerized service that helps you verify and filter email addresses without compromising privacy. Designed with data protection in mind, it performs syntax validation, domain checks, and MX/server-level verification - all without exposing your data to any third-party APIs.

# Install

```
git clone https://github.com/stefanpejcic/emailfilter emailfilter && cd emailfilter && docker compose up --build -d
```

that's it! It's now available locally on `localhost:8080` and you can query it with the following commands:

# Usage

- Check email:
```
curl -X POST "http://localhost:8000/filter-email" \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com"}'
```

- Add domain to whitelist:
```
curl -X POST "http://localhost:8000/whitelist?domain=example.com"
```

- Remove domain from whitelist:
```
curl -X DELETE "http://localhost:8000/whitelist?domain=example.com"
```

- Add domain to blacklist:
```
curl -X POST "http://localhost:8000/blacklist?domain=example.com"
```

- Remove domain from blacklist:
```
curl -X DELETE "http://localhost:8000/blacklist?domain=example.com"
```

- Report as spam:
```
curl -X POST "http://localhost:8000/feedback/spam" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com"}'
```

- Update disposable domains list:
```
wget -O lists/disposable_domains.txt https://disposable.github.io/disposable-email-domains/domains.txt
```

# Production use-cased

## 📤 Exim Outgoing Email Verification

This guide shows how to configure Exim to use emailfilter to verify outgoing emails before delivery. This helps reduce bounces, avoid spam traps, and improve delivery hygiene.

**🧱 Prerequisites:**

- Exim 4 installed and configured for sending mail.
- emailfilter already running locally (default on http://localhost:8000)
- Internet access from the machine (for DNS & MX lookups).

## 🔧 1: Custom Router for Exim

Add a router in Exim to call `emailfilter` before proceeding with delivery.

Edit your `exim4.conf.template` or main config file, and add the following **before** the actual remote delivery router (usually `dnslookup` or `smarthost`):

```exim
emailfilter_verify:
  debug_print = "R: emailfilter_verify for $local_part@$domain"
  driver = redirect
  condition = ${run{/usr/local/bin/emailfilter-check.sh $local_part@$domain}{$value}fail}
  data = :blackhole:
```

This uses a small helper script to call `emailfilter`, and if the result is bad (e.g., invalid domain, blacklisted), the mail is discarded (`:blackhole:`) or rejected.

---

## 🧾 2: Copy `emailfilter-check` script

Copy `scripts/emailfilter-check.sh` to the Exim server a at `/usr/local/bin/emailfilter-check.sh`, and make it executable:

```bash
chmod +x /usr/local/bin/emailfilter-check.sh
```

---

## 🧪 3: Test the Integration

Run a test email and observe logs:

```bash
sendmail test@example.com
```

* Check `/var/log/exim4/mainlog`
* You should see lines like:

  ```
  R: emailfilter_verify for test@example.com
  ```

If the email fails verification, it should be dropped or logged as rejected.

---

## 🧰 Optional: Reject Instead of Dropping

Change the router to **reject** instead of blackhole:

```exim
data = :fail: Email rejected by emailfilter verification.
```

---

## 
