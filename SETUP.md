# PIDA – Setup Guide

This document describes how to deploy and test the PIDA reference implementation.
The setup is intentionally minimal and can typically be completed within 30 minutes.

---

## Requirements

### Client environment
- A modern web browser  
  - Chromium-based browsers  
  - Firefox  
- Supported network contexts:
  - `http://localhost`
  - `https://<your-domain>`

No browser extensions or additional dependencies are required.

---

## Relay environment

### Serverless platform
- Recommended: **Cloudflare Workers**

Other serverless platforms may work, but Cloudflare Workers is the reference environment.

### Relay storage
- Temporary message storage only
- Recommended: **Cloudflare KV**

Storage requirements are minimal because:
- Messages are fetched by clients
- Messages are deleted after explicit ACK
- Messages expire automatically via TTL

---

## Deployment steps

### 1. Create a Cloudflare Worker
- Create a new Worker
- Copy and paste the provided `worker.js` source code

### 2. Create a KV namespace
- Create a Cloudflare KV namespace
- Bind it to the Worker with the variable name:
`PIDA_KV`

⚠️ The binding name **must** be exactly `PIDA_KV` to match the reference implementation.

### 3. Configure TTL
- Set message TTL to **5 days**
- TTL is enforced at the relay level

### 4. Deploy the Worker
- Deploy using `wrangler` or the Cloudflare dashboard
- Note the public Worker URL

---

## Client setup

### 1. Client code
- Use the provided `index.html`
- No build step required

### 2. Hosting
- Open locally via `http://localhost`, or
- Host as a static file (e.g. GitHub Pages, Cloudflare Pages)

### 3. Configuration
- Enter the relay URL in the client UI
- Generate or paste an Inbox UUID
- The client stores inbox data locally using IndexedDB

---

## Security model notes

- All message encryption and decryption happens client-side
- The relay never has access to plaintext data
- The relay is treated as untrusted infrastructure
- Messages are removed from the relay only via:
  - Explicit ACK from the client, or
  - TTL expiration

---

## Rationale for Cloudflare Workers

Cloudflare Workers is used as the reference relay because:
- Very low global latency
- Globally distributed edge network
- Simple deployment model
- No persistent server management required

---

## Expected setup time

With copy-paste deployment:
- **~30 minutes** is typical for a first-time setup