# EmailFilter 📨🔐
Self-hosted, privacy-focused email verification

emailfilter is a lightweight, self-hosted containerized API service that helps you verify and filter email addresses without compromising privacy. Designed with data protection in mind, it performs syntax validation, domain checks, and MX/server-level verification - all without exposing your data to any third-party APIs.


# Install

**Requirements:**
- **Docker** and **docker compose**
- **TCP_OUT** port `43` (for whois checks)

```
git clone https://github.com/stefanpejcic/emailfilter emailfilter && cd emailfilter && docker compose up --build -d
```

that's it! It's now available locally on `localhost:8080` and you can query it with the following commands:

# API Usage

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


- View all lists:
```
curl -X GET "http://localhost:8000/lists"
```

- View a specific list:
```
curl -X GET "http://localhost:8000/lists/<whitelist|blacklist|disposable|spam_keywords>"
```

- Delete a specific list:
```
curl -X DELETE "http://localhost:8000/lists/<whitelist|blacklist|disposable|spam_keywords>"
```

- Report as spam:
```
curl -X POST "http://localhost:8000/feedback/spam" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com"}'
```

- List scores:
```
curl -X GET "http://localhost:8000/scores"
```

- Update scores:
```
curl -X POST http://localhost:8000/scores \
  -H "Content-Type: application/json" \
  -d '{
    "base": 40,
    "mx_exists": 25,
    "new_domain": -10,
    "smtp_valid": 15,
    "disposable": -25,
    "blacklisted": -50
    "whitelisted": 50,
    "spam_keywords": -40
  }'
```

- Restore default scores:
```
curl -X POST http://localhost:8000/scores/default
```


- Update disposable domains list:
```
wget -O lists/disposable_domains.txt https://disposable.github.io/disposable-email-domains/domains.txt
```

# Use-cases:
Below you can find examples on how to setup Exim or Proxmox to use the emailfilter:

- [📤 Exim Outgoing Email Verification](#-exim-incoming-email-filtering)
- [📥 Exim Incoming Email Filtering](#-exim-incoming-email-filtering)
- [🚧 Proxmox Mail Gateway Incoming Email Filtering](#-proxmox-mail-gateway-incoming-email-filtering)


## 📤 Exim Outgoing Email Verification

This guide shows how to configure Exim to use emailfilter to verify outgoing emails before delivery. This helps reduce bounces, avoid spam traps, and improve delivery hygiene.

**Prerequisites:**

- Exim 4 installed and configured for sending mail.
- emailfilter already running locally (default on http://localhost:8000)
- Internet access from the machine (for DNS & MX lookups).

### 1: Create custom router for Exim

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

### 2: Copy `emailfilter-check.sh` script

Copy `scripts/emailfilter-check.sh` to the Exim server at `/usr/local/bin/emailfilter-check.sh`, and make it executable:

```bash
chmod +x /usr/local/bin/emailfilter-check.sh
```

---

### 3: Test

Run a test email and observe logs:

```bash
sendmail test@example.com
```

* Check `/var/log/exim4/mainlog`
* You should see lines like: `R: emailfilter_verify for test@example.com`

If the email fails verification, it should be dropped or logged as rejected.

---

## Optional: Reject Instead of Dropping

Change the router to **reject** instead of blackhole:

```exim
data = :fail: Email rejected by emailfilter verification.
```

---

## 📥 Exim Incoming Email Filtering

Here is how to configure Exim to call `emailfilter` during the **RCPT** stage to check the **sender's email address** and reject bad ones before accepting delivery:


**Prerequisites:**

* Exim running as an SMTP server (receiving mail).
* `emailfilter` running on `http://localhost:8000`.
* Exim compiled with support for `ACLs`.

---

### 1: Create ACL to use *emailfilter*

Edit your Exim configuration (typically in `/etc/exim4/exim4.conf.template` or split config files under `/etc/exim4/conf.d/`):

Find the ACL section called `acl_check_rcpt` (this is where recipient validation and spam checks happen) and add the following block **near the top**:

```exim
  # Check sender address using emailfilter
  warn
    set acl_m0 = ${run{/usr/local/bin/emailfilter-check.sh $sender_address}{$value}fail}

  deny
    condition = ${if eq{$acl_m0}{} {yes}{no}}
    message = Sender address <$sender_address> rejected by emailfilter verification.
```

---

### 2: Copy `emailfilter-check.sh` script

Copy `scripts/emailfilter-check.sh` to the Exim server at `/usr/local/bin/emailfilter-check.sh`, and make it executable:

```bash
chmod +x /usr/local/bin/emailfilter-check.sh
```

---

### 3: Test

Use `telnet`, `swaks`, or just send test emails from a mail client. You should see messages like: `550 Sender address <some@disposablemail.com> rejected by emailfilter verification.`

And in logs: `Sender rejected by acl_check_rcpt: emailfilter`

---

### Optional: Only Filter External Senders

To skip verification for trusted internal senders, you can wrap the check:

```exim
  warn
    condition = ${if !match{$sender_host_address}{^192\.168\.|^10\.} {yes}{no}}
    set acl_m0 = ${run{/usr/local/bin/emailfilter-check $sender_address}{$value}fail}
```

---

## 🚧 Proxmox Mail Gateway Incoming Email Filtering

Here is how to integrate *emailfilter* with **Proxmox Mail Gateway (PMG)** to filter incoming emails based on sender address validation using the emailfilter service:

**Prerequisites:**
- Proxmox Mail Gateway 7.x or newer installed and configured.
- emailfilter service running locally and accessible on http://localhost:8000.
- Root or administrative access to your Proxmox Mail Gateway.

### 1: Copy `pmg-emailfilter-milter.sh` script

Copy `scripts/pmg-emailfilter-milter.sh` to the Exim server at `/usr/local/bin/pmg-emailfilter-milter.sh`, and make it executable:

```bash
chmod +x /usr/local/bin/pmg-emailfilter-milter.sh
```

---

### 2: Configure PMG to use it

Edit the PMG configuration to add this script as a Milter:

- Go to `/etc/postfix/main.cf` on the PMG server.
- Add or modify the `smtpd_milters` parameter to include the script via `milter-regex` or use `milter-greylis` or a generic milter handler depending on your setup.
- Restart postfix: `systemctl restart postfix`

---

### 3: Test

Try sending emails from addresses that are invalid or disposable and verify that PMG rejects them with a 550 error referencing emailfilter.

Check `/var/log/mail.log` or PMG logs for rejection messages.

---

# Troubleshooting

- `ERROR:utils_async:[WHOIS Exception] [Errno 111] Connection refused` means that outgoing connection via port `43` to whois servers is not working. Make sure TCP_OUT port `43` is opened on firewall, test using: `telnet whois.verisign-grs.com 43`
- `curl: (52) Empty reply from server`- indicates that the application did not start correctly - check the logs: `docker logs -f emailfilter`
- *Public IPv4 address not visible in the logs!* - use a reverse proxy and pass the `X-Forwarded-For` header.

# Todo

- routes to display domains penalty and checked domains
- 
