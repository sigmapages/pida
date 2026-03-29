import requests
import uuid
import time
import hashlib
import json
import base64
import os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AEaead


class PIDA:
    def __init__(self, relay_url, seed_uuid):
        self.relay_url = relay_url
        self.id = seed_uuid
        
        # TÍNH DETERMINISTIC: Tạo Private Key từ UUID
        seed = hashlib.sha256(self.id.encode()).digest()
        self.private_key = ec.derive_private_key(
            int.from_bytes(seed, "big"), 
            ec.SECP256R1()
        )
        
        self.public_key = self.private_key.public_key()
        self.pub_key_pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

    @classmethod
    def create(cls, relay_url):
        """Lệnh 1: Tạo mới hoàn toàn một Identity (UUIDv4/v8)"""
        new_uuid = str(uuid.uuid4()) # Hoặc logic v8 của ông
        print(f"✨ Đã tạo Identity mới: {new_uuid}")
        print("⚠️ Hãy lưu UUID này lại, mất là mất luôn tài khoản!")
        return cls(relay_url, new_uuid)

    @classmethod
    def import_id(cls, relay_url, existing_uuid):
        """Lệnh 2: Nhập Identity cũ để khôi phục cặp khóa"""
        print(f"🔑 Đang khôi phục Identity: {existing_uuid}")
        return cls(relay_url, existing_uuid)

    # --- IDENTITY & UUIDv8 ---
    def create_identity(self):
        # Tạo cặp khóa ECDSA (p256)
        self.priv_key = ec.generate_private_key(ec.SECP256R1())
        self.pub_key = self.priv_key.public_key()
        
        # UUIDv8 giả lập (Custom bits): 48 bit timestamp + random
        # Trong Python, uuid.uuid8() có trong bản 3.12+, tui viết custom cho tương thích
        self.id = str(uuid.uuid4()) # Thay bằng logic UUIDv8 nếu cần sortable
        self.priv_key_pem = self.priv_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
        self.pub_key_pem = self.pub_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

    def load_identity(self, data):
        self.id = data['id']
        self.priv_key = serialization.load_pem_private_key(data['priv'].encode(), password=None)
        self.pub_key = self.priv_key.public_key()

    # --- CRYPTO: E2EE & ECDH ---
    def _get_shared_secret(self, peer_pub_pem):
        peer_pub = serialization.load_pem_public_key(peer_pub_pem.encode())
        shared_key = self.priv_key.exchange(ec.ECDH(), peer_pub)
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b'pida-e2ee').derive(shared_key)

    def encrypt_msg(self, peer_pub_pem, plaintext):
        key = self._get_shared_secret(peer_pub_pem)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ct).decode()

    def decrypt_msg(self, peer_pub_pem, ciphertext):
        key = self._get_shared_secret(peer_pub_pem)
        data = base64.b64decode(ciphertext)
        nonce, ct = data[:12], data[12:]
        return AESGCM(key).decrypt(nonce, ct, None).decode()

    # --- PROTOCOL: PoW & SYNC ---
    def _compute_pow(self, data, diff=4):
        nonce = 0
        while True:
            h = hashlib.sha256(f"{data}{nonce}".encode()).hexdigest()
            if h.startswith('0' * diff): return {"nonce": nonce, "hash": h}
            nonce += 1

    def send_message(self, to_id, peer_pub_pem, content, is_file=False):
        encrypted_content = self.encrypt_msg(peer_pub_pem, content)
        msg_id = str(uuid.uuid4())
        msg = {
            "id": msg_id, "from": self.id, "to": to_id,
            "content": encrypted_content, "type": "file" if is_file else "text",
            "timestamp": int(time.time() * 1000), "sender_pub": self.pub_key_pem
        }
        pow_data = self._compute_pow(msg_id)
        return requests.post(f"{self.relay}/send", json={"msg": msg, "pow": pow_data}).json()

    def sync(self):
        # Challenge-Response
        res = requests.get(f"{self.relay}/challenge?address={self.id}").json()
        challenge = res['challenge']
        signature = self.priv_key.sign(challenge.encode(), ec.ECDSA(hashes.SHA256()))
        
        payload = {
            "address": self.id, "challenge": challenge,
            "signature": base64.b64encode(signature).decode()
        }
        msgs = requests.post(f"{self.relay}/get", json=payload).json().get('messages', [])
        
        for m in msgs:
            if m['from'] in self.block_list:
                self.ack(m['id'])
                continue
            # Thử giải mã nếu có sender_pub
            try:
                m['body'] = self.decrypt_msg(m['sender_pub'], m['content'])
            except: m['body'] = "[Decryption Failed]"
            self.inbox.append(m)
        return self.inbox

    def ack(self, msg_id):
        requests.post(f"{self.relay}/ack", json={"id": msg_id, "address": self.id})

    def backup_inbox(self, filename="inbox_backup.json"):
        with open(filename, 'w') as f:
            json.dump(self.inbox, f)