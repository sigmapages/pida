# PIDA Protocol v1

## Overview

PIDA (Private Inbox Data API) is a protocol for asynchronous,
inbox-based messaging where users own their inbox data.

## Message Schema

```json
{
  "id": "UUID",
  "to": "UUID",
  "fromUUID": "UUID",
  "fromNick": "string",
  "cipher": "base64",
  "iv": "base64",
  "createdAt": 1700000000000
}
```
##Delivery Flow
1.Sender encrypts message locally
2.Sender POSTs message to relay
3.Relay stores message temporarily
4.Receiver fetches inbox explicitly
5.Receiver stores message locally
6.Receiver sends ACK
7.Relay deletes acknowledged messages
##Storage
- Relay storage is temporary only
- Clients are responsible for local persistence
##TTL
Default message TTL: 5 days
##Non-goals
- Real-time messaging
- Presence or online status
- Centralized identity
