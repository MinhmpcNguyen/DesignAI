# Credential mapping

| Bundle item | Current configuration name | Actual meaning |
|---|---|---|
| `public_key.txt` | `OPENAI_PUBLIC_KEY` | Secret Fernet symmetric key |
| `private_key.enc` | `OPENAI_PRIVATE_KEY_FILE` | Fernet-encrypted API key |
| `.env` | Runtime environment | Contains the Fernet key and Azure/OpenAI settings |

The current decryption operation is equivalent to:

```python
from cryptography.fernet import Fernet

cipher = Fernet(openai_public_key)
api_key = cipher.decrypt(encrypted_api_key).decode()
```

This is symmetric authenticated encryption, not public-key cryptography.

