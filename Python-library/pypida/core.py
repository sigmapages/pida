import requests
import uuid
import base64
import hashlib, uuid, os, json, requests
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class PIDA:
    CONFIG_FILE = ".pida_config"

    def __init__(self, relay_url, seed_uuid):
        self.relay_url = relay_url
        self.id = seed_uuid
        # Deterministic Key Derivation: UUID -> SHA256 -> P-256 Private Key
        seed = hashlib.sha256(self.id.encode()).digest()
        self.private_key = ec.derive_private_key(int.from_bytes(seed, "big"), ec.SECP256R1())
        self.public_key = self.private_key.public_key()
        self.pub_key_pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

    @classmethod
    def create(cls, relay_url, save_local=True):
        new_id = str(uuid.uuid4())
        client = cls(relay_url, new_id)
        if save_local: client._save_config()
        return client

    @classmethod
    def import_id(cls, relay_url, existing_uuid, save_local=True):
        client = cls(relay_url, existing_uuid)
        if save_local: client._save_config()
        return client

    @classmethod
    def load_local(cls, relay_url):
        if os.path.exists(cls.CONFIG_FILE):
            with open(cls.CONFIG_FILE, "r") as f:
                return cls(relay_url, json.load(f)["uuid"])
        return None

    def _save_config(self):
        # Thử lưu, nếu chmod không được thì cũng không crash app
        try:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump({"uuid": self.id}, f)
            
            if os.name != 'nt':
                os.chmod(self.CONFIG_FILE, 0o600)
                # Kiểm tra lại xem chmod có thực sự ăn không
                mode = stat.S_IMODE(os.stat(self.CONFIG_FILE).st_mode)
                if mode != 0o600:
                    print("⚠️ Note: File is on a storage that doesn't support chmod (e.g. SD Card)")
        except Exception as e:
            print(f"❌ Save config failed: {e}")

    def encrypt(self, data, peer_pub_pem):
        peer_pub = serialization.load_pem_public_key(peer_pub_pem.encode())
        shared_key = self.private_key.exchange(ec.ECDH(), peer_pub)
        derived_key = hashlib.sha256(shared_key).digest()
        aesgcm = AESGCM(derived_key)
        nonce = os.urandom(12)
        return nonce + aesgcm.encrypt(nonce, data.encode(), None)

    # Thêm các hàm sync/send/ack tùy theo logic Worker của ông ở đây
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