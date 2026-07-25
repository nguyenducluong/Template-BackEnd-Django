# 1. MÃ£ hÃ³a API 2 chiá»u â€” Handshake + AES-256-GCM

> Tá»± Ä‘á»™ng **Táº®T** khi `DJANGO_ENV=development` (response/request tráº£ plaintext).
> Báº­t khi `DJANGO_ENV=staging|production`.

## 1.1 Táº¡o keypair

**Server** (cháº¡y 1 láº§n trÃªn mÃ¡y server):

```powershell
# PRIVATE KEY â€” táº¡o má»›i
C:\xampp\apache\bin\openssl genrsa -out certs\private_key.pem 4096
# PUBLIC KEY â€” tÃ¡i táº¡o tá»« private key
C:\xampp\apache\bin\openssl rsa -pubout -in certs\private_key.pem -out certs\public_key.pem
```

**Client** (má»—i client/á»©ng dá»¥ng táº¡o keypair riÃªng, lÃ m y há»‡t). Client giá»¯
`private_key.pem` bÃ­ máº­t; chá»‰ gá»­i **public key** lÃªn server lÃºc handshake.

## 1.2 Flow hoáº¡t Ä‘á»™ng

```
CLIENT                                     SERVER
  |                                          |
  | 1. POST /api/v1/crypto/handshake         |
  |    { "public_key": "<PEM client>" }      |
  |----------------------------------------->|
  |                                          | 2. Sinh AES-256 session key
  |                                          |    LÆ°u Redis (TTL 1h, sliding)
  | 3. { session_id,                         |    Wrap AES key báº±ng RSA-OAEP
  |      key: <AES key wrap báº±ng pub client>,|    public key cá»§a CLIENT
  |      payload, nonce (probe AES-GCM),     |
  |      expires_in }                        |
  |<-----------------------------------------|
  |                                          |
  | 4. Giáº£i mÃ£ `key` báº±ng private key client |  (verify probe: giáº£i mÃ£
  |    -> cÃ³ AES session key                 |   payload/nonce báº±ng session key)
  |                                          |
  | 5. Request mÃ£ hÃ³a:                       |
  |    X-Session-Id: <session_id>            |
  |    Content-Type: application/encrypted+json
  |    { payload: <b64 AES-GCM>, nonce }     |
  |----------------------------------------->| 6. Giáº£i mÃ£ báº±ng session key
  |                                          |    -> DRF parse/validate bÃ¬nh thÆ°á»ng
  | 7. Response mÃ£ hÃ³a cÃ¹ng session key:     |
  |    Content-Type: application/encrypted+json
  |    { payload, nonce }                    |
  |<-----------------------------------------|
  | 8. Giáº£i mÃ£ báº±ng session key              |
```

- Session háº¿t háº¡n (1h khÃ´ng dÃ¹ng) â†’ client handshake láº¡i.
- Request **khÃ´ng** kÃ¨m `X-Session-Id`/content-type encrypted â†’ Ä‘i qua
  plaintext (tÆ°Æ¡ng thÃ­ch admin, health, docs).
- Tamper payload (sai tag GCM) â†’ server tráº£ HTTP 400.

## 1.3 VÃ­ dá»¥ code Client (Python)

```python
import base64, json, os, requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

BASE = "https://server.example.com"
OAEP = padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)

# ---- 1 láº§n khi khá»Ÿi Ä‘á»™ng: handshake ----
priv = serialization.load_pem_private_key(open("client_private_key.pem","rb").read(), None)
pub_pem = priv.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()

hs = requests.post(f"{BASE}/api/v1/crypto/handshake/",
                   json={"public_key": pub_pem}).json()["data"]
sess_key = priv.decrypt(base64.b64decode(hs["key"]), OAEP)   # AES-256 session key
SESSION = hs["session_id"]

# ---- má»—i request ----
def enc(obj):
    n = os.urandom(12)
    return {"payload": base64.b64encode(AESGCM(sess_key).encrypt(n, obj, None)).decode(),
            "nonce": base64.b64encode(n).decode()}

r = requests.post(f"{BASE}/api/v1/accounts/auth/login/",
                  headers={"X-Session-Id": SESSION, "Content-Type": "application/encrypted+json"},
                  json=enc(json.dumps({"account": "18764398", "password": "..."}).encode()))
res = json.loads(AESGCM(sess_key).decrypt(base64.b64decode(r.json()["nonce"]),
                                          base64.b64decode(r.json()["payload"]), None))
print(res["access"])
```

## 1.4 VÃ­ dá»¥ Client (JavaScript / Node `node-forge` + WebCrypto tÆ°Æ¡ng Ä‘Æ°Æ¡ng)

```js
// DÃ¹ng thÆ° viá»‡n node-forge cho RSA-OAEP + AES-GCM
const forge = require("node-forge");
// 1. sinh keypair client 1 láº§n (forge.rsa.generateKeyPair)
// 2. handshake -> POST { public_key: forge.pki.publicKeyToPem(pub) }
// 3. sessKey = privKey.decrypt(forge.util.decode64(hs.key), "RSA-OAEP", {md: forge.md.sha256.create()})
// 4. mÃ£ hÃ³a AES-256-GCM báº±ng sessKey; giáº£i mÃ£ response nhÆ° vÃ­ dá»¥ Python á»Ÿ trÃªn
```

## 1.5 Cáº¥u hÃ¬nh server liÃªn quan (.env)

```env
DJANGO_ENV=production            # development = táº¯t mÃ£ hÃ³a
RSA_PRIVATE_KEY_PATH=certs/private_key.pem
RSA_PUBLIC_KEY_PATH=certs/public_key.pem
CRYPTO_SESSION_TTL=3600
```

## 1.6 Payload lá»›n (vÃ i MB Ä‘áº¿n ~15MB)

**CÆ¡ cháº¿ Ä‘Ã£ sáºµn sÃ ng cho payload lá»›n:** RSA chá»‰ dÃ¹ng trao Ä‘á»•i AES key (32
bytes); toÃ n bá»™ payload Ä‘i qua AES-256-GCM (tá»‘c Ä‘á»™ ~1GB/s). ÄÃ£ Ä‘o thá»±c táº¿
(server local):

| Payload | AES encrypt | Request + response qua server | Status |
|---|---|---|---|
| 1 MB | ~0 ms | ~490 ms (gá»“m login + DB) | 200 |
| 10 MB | ~7 ms | ~560 ms | 200 |

**Cáº¥u hÃ¬nh liÃªn quan (`.env`):**

```env
# Giá»›i háº¡n plaintext request (bytes) â€” máº·c Ä‘á»‹nh 15MB
ENCRYPTION_MAX_BODY_SIZE=15728640
```

- Middleware **tá»« chá»‘i sá»›m (400 "Payload too large")** request vÆ°á»£t háº¡n má»©c
  trÆ°á»›c khi buffer vÃ o RAM â†’ chá»‘ng abuse
- `DATA_UPLOAD_MAX_MEMORY_SIZE` (Django) tá»± set â‰¥ `ENCRYPTION_MAX_BODY_SIZE`
- Web server cÅ©ng pháº£i cho qua: **Nginx** `client_max_body_size 25m;`
  (Ä‘Ã£ cÃ³ trong `started/deploy/nginx.conf`), **Apache/XAMPP** `LimitRequestBody`
  (máº·c Ä‘á»‹nh cho phÃ©p)

**LÆ°u Ã½ quan trá»ng:**

1. **GCM lÃ  all-or-nothing**: há»ng 1 byte â†’ fail cáº£ payload. OK cho â‰¤15MB;
   náº¿u cáº§n >50MB nÃªn **chunk** thÃ nh nhiá»u request hoáº·c dÃ¹ng TLS thuáº§n.
2. **Upload file (multipart)**: KHÃ”NG gá»­i qua encrypted JSON. Upload file
   tháº³ng báº±ng `multipart/form-data` qua **HTTPS** â€” TLS Ä‘Ã£ mÃ£ hÃ³a truyá»n
   dáº«n; mÃ£ hÃ³a JSON chá»‰ dÃ nh cho dá»¯ liá»‡u JSON business.
3. Body 10MB Ä‘Æ°á»£c giá»¯ trong RAM ~2 láº§n (ciphertext + plaintext) per request
   â€” vá»›i traffic lá»›n hÃ£y giÃ¡m sÃ¡t memory server.


ÄÆ°á»ng dáº«n Ä‘Æ°á»£c loáº¡i trá»« mÃ£ hÃ³a: `/admin`, `/api/v1/health`, `/api/v1/crypto`,
`/api/schema`, `/api/docs`, `/api/redoc`, `/static`, `/media`.

