import unittest
import hashlib
from pypida import PIDA

class TestPIDAProtocol(unittest.TestCase):
    def setUp(self):
        self.relay_url = "https://pida-worker.example.dev"
        self.test_uuid = "6be1438c-2114-42bf-a6eb-aabe55bc8a86"

    def test_create_identity(self):
        """Kiểm tra tạo mới Identity có sinh đủ ID và PubKey không"""
        client = PIDA.create(self.relay_url)
        self.assertIsNotNone(client.id)
        self.assertTrue(client.pub_key_pem.startswith("-----BEGIN PUBLIC KEY-----"))
        print(f"\n✅ Test Create: OK (ID: {client.id[:8]}...)")

    def test_deterministic_import(self):
        """TRỌNG TÂM: Kiểm tra cùng 1 UUID nhập vào phải ra cùng 1 Public Key"""
        client1 = PIDA.import_id(self.relay_url, self.test_uuid)
        client2 = PIDA.import_id(self.relay_url, self.test_uuid)
        
        # So sánh toàn bộ chuỗi PEM của Public Key
        self.assertEqual(client1.pub_key_pem, client2.pub_key_pem)
        
        # Kiểm tra tính khớp lệnh của ID
        self.assertEqual(client1.id, self.test_uuid)
        print(f"✅ Test Deterministic: PASSED (Keys are identical for UUID {self.test_uuid[:8]})")

    def test_key_security(self):
        """Kiểm tra 2 UUID khác nhau phải ra 2 cặp khóa khác nhau"""
        uuid_a = "00000000-0000-0000-0000-000000000001"
        uuid_b = "00000000-0000-0000-0000-000000000002"
        
        client_a = PIDA.import_id(self.relay_url, uuid_a)
        client_b = PIDA.import_id(self.relay_url, uuid_b)
        
        self.assertNotEqual(client_a.pub_key_pem, client_b.pub_key_pem)
        print("✅ Test Security: OK (Different UUIDs produce different keys)")

if __name__ == '__main__':
    print("--- RUNNING PIDA PROTOCOL SUITE ---")
    unittest.main()