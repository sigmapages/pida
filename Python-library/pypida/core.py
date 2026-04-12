import hashlib, uuid, os, json, requests, time, base64, stat
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class PIDA:
    CONFIG_FILE = ".pida_config"

    def __init__(self, relay_url, seed_uuid):
        self.relay = relay_url.rstrip('/')
        self.id = seed_uuid
        self.inbox = []
        
        # --- DERIVE KEYS (ECDH P-256) --- 
        seed = hashlib.sha256(self.id.encode()).digest()
        self.priv_key = ec.derive_private_key(int.from_bytes(seed, "big"), ec.SECP256R1())
        self.public_key = self.priv_key.public_key()
        self.pub_key_pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

    @classmethod
    def import_id(cls, relay_url, existing_uuid, save_local=True):
        client = cls(relay_url, existing_uuid)
        if save_local: client._save_config()
        return client

    def _save_config(self):
        try:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump({"uuid": self.id}, f)
        except Exception as e:
            print(f"❌ Save config failed: {e}")

    # --- CRYPTO HELPERS --- 
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

    # --- CORE PROTOCOL --- 
    def health(self):
        try: return requests.get(f"{self.relay}/health").json()
        except: return {"status": "offline"}

    def send_message(self, to_id, peer_pub_pem, content, is_file=False):
        encrypted_content = self.encrypt_msg(peer_pub_pem, content)
        msg_id = str(uuid.uuid4())
        msg = {
            "id": msg_id, "from": self.id, "to": to_id,
            "content": encrypted_content, "type": "file" if is_file else "text",
            "timestamp": int(time.time() * 1000), "sender_pub": self.pub_key_pem
        }
        return requests.post(f"{self.relay}/send", json={"msg": msg}).json()

    # --- UPLOAD & DOWNLOAD FILE THẬT ---
    def upload_file(self, to_id, peer_pub_pem, filepath):
        """Tải file thật lên B2 và gửi thông báo cho đối phương"""
        if not os.path.exists(filepath):
            return {"success": False, "error": "File not found"}

        file_name = os.path.basename(filepath)
        file_id = str(uuid.uuid4())[:8] # Tạo ID ngắn gọn cho file

        print(f"📤 Đang tải file lên B2: {file_name}...")
        with open(filepath, 'rb') as f:
            file_data = f.read()

        # 1. Gửi dữ liệu nhị phân lên Worker (Worker cần endpoint xử lý b2Upload)
        # Ở bản Worker hiện tại, chúng ta lợi dụng /send nhưng gửi body là binary 
        # Hoặc dùng endpoint chuyên dụng nếu ông đã thêm vào Worker
        upload_res = requests.post(
            f"{self.relay}/upload?id={file_id}", 
            data=file_data,
            headers={'Content-Type': 'application/octet-stream'}
        )

        if upload_res.status_code == 200:
            print(f"✅ Đã lưu file trên B2. Đang gửi link cho đối phương...")
            # 2. Gửi tin nhắn chứa "chìa khóa" để bên kia tải
            content = f"FILE_SHARE:{file_id}|NAME:{file_name}"
            return self.send_message(to_id, peer_pub_pem, content, is_file=True)
        else:
            return {"success": False, "error": upload_res.text}

    def download_file(self, file_id, file_name):
        """Tải file từ B2 về máy thông qua Worker"""
        print(f"📥 Đang tải file: {file_name}...")
        url = f"{self.relay}/f/{file_id}/{file_name}"
        res = requests.get(url)
        
        if res.status_code == 200:
            with open(file_name, 'wb') as f:
                f.write(res.content)
            print(f"✅ Đã lưu file: {os.path.abspath(file_name)}")
            return True
        else:
            print(f"❌ Không tải được file: {res.status_code}")
            return False

    def sync(self):
        try:
            res = requests.get(f"{self.relay}/challenge?address={self.id}").json()
            challenge = res['challenge']
            signature = self.priv_key.sign(challenge.encode(), ec.ECDSA(hashes.SHA256()))
            
            payload = {
                "address": self.id, "challenge": challenge,
                "signature": base64.b64encode(signature).decode()
            }
            resp = requests.post(f"{self.relay}/get", json=payload)
            msgs = resp.json().get('messages', [])
            
            new_msgs = []
            for m in msgs:
                try: m['body'] = self.decrypt_msg(m['sender_pub'], m['content'])
                except: m['body'] = "[Decryption Failed]"
                new_msgs.append(m)
            self.inbox = new_msgs
            return new_msgs
        except Exception as e:
            print(f"❌ Sync Failed: {e}")
            return []
    def clear_bucket(self):
        """Dọn sạch toàn bộ dữ liệu trên Bucket (msgs, challenges, files)"""
        print("🧹 Đang tiến hành dọn dẹp Bucket... Vui lòng chờ...")
        try:
            res = requests.post(f"{self.relay}/clear")
            if res.status_code == 200:
                data = res.json()
                print(f"✅ Đã dọn sạch {data.get('deleted', 0)} tệp tin. Bucket hiện đã trống!")
                return True
            else:
                print(f"❌ Lỗi dọn dẹp: {res.text}")
                return False
        except Exception as e:
            print(f"❌ Không thể kết nối để dọn dẹp: {e}")
            return False

