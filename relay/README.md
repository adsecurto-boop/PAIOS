# PAIOS Relay

A tiny, dependency-free reverse-tunnel broker that lets your phone reach
your PAIOS desktop from **any** network — home Wi-Fi, office Wi-Fi, or
mobile data — without exposing your computer to the internet.

Your desktop dials **out** to the relay and long-polls it; the phone
talks only to the relay. Neither the desktop nor the phone ever accepts
an inbound connection, so nothing on your laptop is exposed. The relay
only ever forwards bytes between an authenticated desktop and its
authenticated phones.

```
Phone  ──HTTPS──▶  Relay  ◀──long-poll (outbound)──  Desktop  ──▶  Ollama
        (JWT)                (this service)               (PAIOS API)
```

## Run it

Python 3.12+ and nothing else:

```bash
python relay.py
```

or with Docker:

```bash
cp .env.example .env    # then edit the secrets
docker compose up -d
```

Deploy it on Oracle Cloud (always-free tier works), a Raspberry Pi,
DigitalOcean, Hetzner, AWS, Azure — anywhere reachable from the
internet. No PAIOS code changes to move it.

## Configure (environment variables only)

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `PAIOS_RELAY_SECRET` | yes | — | HS256 signing secret for phone tokens |
| `PAIOS_RELAY_ACCOUNT_KEY` | yes | — | the desktop's shared credential |
| `PAIOS_RELAY_ACCOUNT` | no | `default` | account id (one desktop) |
| `PAIOS_RELAY_HOST` | no | `0.0.0.0` | bind host |
| `PAIOS_RELAY_PORT` | no | `8770` | bind port |
| `PAIOS_RELAY_TLS_CERT` / `_KEY` | no | — | serve HTTPS directly |
| `PAIOS_RELAY_POLL_SECONDS` | no | `25` | desktop long-poll window |

Generate secrets:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## TLS

Two supported options:

1. **Reverse proxy (recommended).** Put Caddy, nginx or Traefik in
   front for automatic Let's Encrypt certificates and leave the relay on
   plain HTTP behind it.
2. **Direct HTTPS.** Point `PAIOS_RELAY_TLS_CERT` / `PAIOS_RELAY_TLS_KEY`
   at a PEM certificate and key.

## Security model

- Phones authenticate with short-lived **JWT access tokens** (HS256) and
  rotate them with long-lived **refresh tokens**; a token is bound to one
  account and one device.
- A phone can only obtain a token after the **desktop authorizes its
  paired device** with the relay — the relay never trusts an unpaired
  phone.
- Every forwarded request carries a **nonce + timestamp**; replays and
  stale requests are rejected.
- The desktop proves itself with `PAIOS_RELAY_ACCOUNT_KEY`
  (constant-time comparison).
- The relay keeps **no PAIOS data** — it only forwards encrypted,
  authenticated requests between an online desktop and its phones.
