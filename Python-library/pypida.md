## 1. Core Requirements
To use the pypida library, the following environment and dependencies are required:

Python: >= 3.7

Dependencies: * cryptography: For ECC (Elliptic Curve Cryptography) operations.

requests: For interacting with the Cloudflare Worker Relay.

hashlib: For deterministic seed generation.

Relay Server: A compatible Cloudflare Worker with KV namespace binding.
---
## 2. Protocol Logic: Deterministic - Identity: Unlike standard PGP or SSH keys that require manual file management, Pypida uses a Deterministic derivation model.

- Input: A unique UUID (v7 or v8 recommended).

- Process: The UUID is hashed via SHA-256, and the resulting 32-byte digest is used as the private scalar for the SECP256R1 (P-256) Elliptic Curve.

- Benefit: Users can recover their identity and cryptographic keys on any device just by providing their UUID, without needing to store sensitive .pem files.
---
## 3. API Reference & Commands
### 1 Initialization & Identity Management
PIDA.create(relay_url)
Generates a brand new random identity.

- Returns: PIDA instance.

- Usage: Use this for first-time users who do not have a UUID.

- PIDA.import_id(relay_url, existing_uuid)
Restores an existing identity using a known UUID.

- Returns: PIDA instance.

- Usage: Crucial for cross-device synchronization and account recovery.

### 2 Messaging Operations
1.send_message(to_id, peer_pub_pem, content)
Encrypts and sends a message to a specific recipient.

- Parameters:

  - to_id: The UUID of the recipient.

  - peer_pub_pem: The recipient's Public Key (PEM format).

  - content: The plaintext string message.

- Process: Includes a Proof of Work (PoW) calculation to prevent spam on the relay.

2.sync() Fetches and decrypts all pending messages for the current identity.

- Process: 1. Requests a cryptographic challenge from the relay.
- Signs the challenge using the Private Key (ECDSA).
- Retrieves encrypted payloads and decrypts them locally.

3.ack(message_id)
Acknowledges receipt of a message, allowing the relay to delete it.

- Usage: Helps keep the KV storage clean and ensures message privacy (Delete-on-Read).
---
## 4. Implementation Example
Python

from pypida import PIDA

### 1. Setup Relay
RELAY = "https://your-pida-worker.workers.dev"

### 2. Restore Identity (Deterministic)
user_uuid = "6be1438c-2114-42bf-a6eb-aabe55bc8a86"
client = PIDA.import_id(RELAY, user_uuid)

### 3. Synchronize Inbox
messages = client.sync()

for msg in messages:
    print(f"From: {msg['from']}")
    print(f"Content: {msg['body']}")
    
### 4. Acknowledge message
    client.ack(msg['id'])
---
### 5. Security Model
- Zero-Knowledge Relay: The Cloudflare - Worker never sees plaintext content. It only stores encrypted blobs.

- Authentication: All GET requests are protected by ECDSA signatures over a one-time challenge.

- Anti-Spam: Integrated Proof-of-Work (PoW) on the client-side to ensure relay resources are protected.