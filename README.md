# PIDA – Private Inbox Data API

PIDA is a decentralized, inbox-first messaging protocol.

Instead of accounts, platforms, or permanent servers,  
PIDA gives users full ownership of their inbox and identity through keys.

Servers act only as temporary, disposable message relays.

This project is submitted to **NLnet / NGI (Next Generation Internet)**  
as an experimental Internet building block.

---

## Key ideas

- Inbox-first, asynchronous communication
- No accounts, no usernames
- Identity via UUID (key-based)
- Serverless or self-hosted relays
- End-to-end encryption on the client
- Local inbox storage (IndexedDB, file local)
- ACK-based delivery and deletion
- TTL-based message expiry

---

## Architecture
Sender Web → PIDA API → Serverless Relay (temporary storage) → Receiver Web → Local Inbox (IndexedDB / file) → ACK → Relay deletes message

---

## Motivation

Most modern messaging systems centralize identity and data.
Even secure messengers rely on trusted servers, platforms, and accounts.

PIDA explores a simpler alternative:
**inbox ownership as a local, movable data structure**,  
where privacy comes from architecture rather than policy.

---

## Status

- PIDA v1
- Working prototype
- Intentionally minimal
- Not designed to replace real-time chat systems

---

## Repository structure
```
pida/ 

├─ README.md 

├─ LICENSE

├─ spec/ │  
       └─ pida.md
  
├─ worker/ │
       └─ worker.js 
       
       
├─ client/ │  
       └─ index.html
```

---

## How to setup
Read the `pida/SETUP.md`

---

## License

GNU Lesser General Public License v3.0 (LGPLv3)
