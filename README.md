# emailfilter 📨🔐
Self-hosted e-mail verification


## Usage


```
git clone https://github.com/stefanpejcic/emailfilter emailfilter && cd emailfilter && docker compose up --build -d
```


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
