<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Application Encryption with AEAD

When application code encrypts data itself, verify the algorithm, the nonce discipline, and the randomness source. Most homegrown crypto fails on one of those three, not on the cipher.

## Use an authenticated cipher (AEAD)

Confidentiality without integrity is exploitable (bit-flipping, padding oracles). Prefer a mode that authenticates.

- Anti-pattern: `aes-256-cbc`, `aes-256-ctr`, or any `-cbc`/`-ctr` string with no separate MAC; `createCipher(` (the keyless, password-derived, deprecated form).
- Anti-pattern: `aes-256-ecb` / any `-ecb` mode — ECB encrypts identical plaintext blocks to identical ciphertext and leaks structure. Never acceptable for data.
- Fix: use an AEAD mode—AES-GCM is available in Node and WebCrypto; XChaCha20-Poly1305
  is available through libsodium, not Node's built-in `crypto` or WebCrypto. Use the exact
  key, nonce, tag-length, and API requirements documented for the selected library.
- If interoperability mandates a non-AEAD mode, use a reviewed encrypt-then-MAC
  construction with independent keys and authenticate an unambiguous encoding of the
  algorithm/version, IV, associated metadata, and ciphertext. Do not invent a format from
  the shorthand “HMAC the ciphertext.”

## AES-256-GCM: never reuse a nonce under one key

GCM nonce reuse under the same key repeats the keystream: XORing the ciphertexts reveals
the XOR of the plaintexts, known plaintext can reveal the other message, and authentication
forgeries become possible.

- Anti-pattern: a fixed/constant IV (`Buffer.alloc(12)`, a hardcoded literal, an IV derived from a counter that resets, or an IV reused across messages); an IV shorter/longer than 12 bytes without deliberate reason.
- Anti-pattern: discarding the authentication tag or failing to provide it during
  decryption. Current Node GCM decryption fails authentication at `final()`; verify the
  failure path and never use plaintext returned by `update()` before successful `final()`.
- Fix: generate a fresh 12-byte (96-bit) IV per message with `crypto.randomBytes(12)`; NIST SP 800-38D recommends restricting GCM IVs to 96 bits for efficiency and interoperability (other lengths are permitted but get hashed internally). Store the IV, tag, ciphertext, algorithm/version, and any AAD contract in an unambiguous format.
- Fix: obtain and store the tag after encryption; provide the tag before finalizing
  decryption and treat any authentication failure as a hard failure. Set and validate the
  intended tag length explicitly where the Node version/API requires it.
- Enforce the construction's per-key invocation limits. For high-volume or long-lived keys,
  use a correctly persisted counter strategy, rotate keys before the applicable GCM limit,
  or use libsodium XChaCha20-Poly1305 with its documented 192-bit random nonce. Verify
  constants and limits against the installed implementation.

## Randomness: CSPRNG for every key, IV, salt, and token

Any key, IV/nonce, salt, or unguessable token derived from a non-cryptographic RNG is predictable and defeats the cipher.

- Anti-pattern: `Math.random()`, `Date.now()`, `process.hrtime()`, PID, or an incrementing counter used to produce a key, IV, salt, session id, reset token, or API key.
- Fix: use Node `crypto.randomBytes(n)`/`randomFillSync`, WebCrypto
  `crypto.getRandomValues`, or the construction's documented generator. Size output for
  its purpose; do not substitute `Math.random()`.

## Avoid broken primitives

- Anti-pattern: `createHash('md5')` / `createHash('sha1')` used for signatures, message integrity, or any tamper-detection role (collisions are practical); `md5`/`sha1` in a signing or HMAC-substitute context.
- Anti-pattern: `des`, `des-ede3` / `des3` (3DES), or `rc4` cipher strings for encryption — obsolete, small block/key or biased keystream.
- Fix: for integrity/signatures use SHA-256 or stronger (or an AEAD tag / HMAC-SHA-256); for encryption use AES-256-GCM or XChaCha20-Poly1305 as above.
- Note: MD5/SHA-1 remain acceptable only for non-security uses (e.g. cache keys, checksums against accidental corruption). Do not flag those, and confirm the algorithm isn't feeding a security decision before clearing it.

Password hashing (Argon2/bcrypt/scrypt) and key derivation are a separate concern — see the storage/secrets guidance and ../../ATTRIBUTION.md. This card covers reversible data encryption only.

## Primary sources

- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [Node.js crypto — Cipher / createCipheriv / randomBytes](https://nodejs.org/api/crypto.html)
- [libsodium — XChaCha20-Poly1305 construction](https://doc.libsodium.org/secret-key_cryptography/aead/chacha20-poly1305/xchacha20-poly1305_construction)
- [NIST SP 800-38D — GCM](https://csrc.nist.gov/pubs/sp/800/38/d/final)
