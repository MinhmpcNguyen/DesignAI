# Current project Azure/OpenAI setup bundle

This bundle copies the OpenAI/Azure configuration, credential material, and
client code from the current `DesignAI/backend` project.

## Important security warning

This directory contains real credential material copied from the current local
project:

- `.env` contains the current environment configuration.
- `public_key.txt` contains the exact value currently stored in
  `OPENAI_PUBLIC_KEY`.
- `private_key.enc` contains the encrypted OpenAI/Azure API credential.

Despite its current name, `OPENAI_PUBLIC_KEY` is not a public RSA key. It is a
Fernet symmetric decryption key and must remain secret. `private_key.enc` is not
an RSA private key; it is the Fernet-encrypted API credential.

Anyone who obtains both `public_key.txt` and `private_key.enc` can decrypt the
API credential. Treat this ZIP as a secret and do not commit or share it.

## Included source files

```text
app-config.yaml
config/__init__.py
config/models.py
config/openai_config.py
clients/base_client.py
clients/openai_client.py
pyproject.toml
uv.lock
```

## Use in another Python project

Copy these paths into the target backend root while keeping the relative
layout:

```text
.env
private_key.enc
app-config.yaml
config/
clients/
```

Install the locked dependencies:

```bash
uv sync --frozen
```

The current configuration loader resolves `private_key.enc` relative to the
backend root. Keep this value in `.env`:

```dotenv
OPENAI_PRIVATE_KEY_FILE=private_key.enc
```

Do not replace the value of `OPENAI_PUBLIC_KEY` unless the API key is encrypted
again with the replacement Fernet key.

## Verify without printing secrets

```bash
uv run python verify_config.py
```

This checks whether the mode, endpoint, credential, and model mappings resolve.
It does not call Azure and does not print the credential.

## Test an Azure request

After verification succeeds, run:

```bash
uv run python smoke_test.py
```

The smoke test makes one small billable model request.

## Docker warning

The copied `.dockerignore` is the exact current project version and does not
exclude `private_key.enc`. Use `.dockerignore.recommended` in the target project
or mount `private_key.enc` as a runtime secret. Do not bake it into an image.
