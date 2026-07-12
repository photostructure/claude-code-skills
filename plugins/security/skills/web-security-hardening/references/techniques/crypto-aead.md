<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Application Encryption with AEAD

When application code encrypts data itself, verify the algorithm, the nonce discipline, and the randomness source. Most homegrown crypto fails on one of those three, not on the cipher.

## Use an authenticated cipher (AEAD)

Confidentiality without integrity is exploitable (bit-flipping, padding oracles). Prefer a mode that authenticates.

- Anti-pattern: `aes-256-cbc`, `aes-256-ctr`, or any `-cbc`/`-ctr` string with no separate MAC; `createCipher(` (the keyless, password-derived, deprecated form).
- Anti-pattern: `aes-256-ecb` / any `-ecb` mode — ECB encrypts identical plaintext blocks to identical ciphertext and leaks structure. Never acceptable for data.
- Fix: use an AEAD mode — Node `crypto.createCipheriv('aes-256-gcm', key, iv)`, WebCrypto `subtle.encrypt({ name: 'AES-GCM', iv }, key, data)`, or libsodium `crypto_aead_xchacha20poly1305_ietf_encrypt(...)`.
- Fix (only if a non-AEAD mode is mandated): encrypt-then-MAC with an independent key (e.g. HMAC-SHA-256 over the ciphertext), and verify the MAC in constant time before decrypting.

## AES-256-GCM: never reuse a nonce under one key

GCM nonce reuse under the same key recovers the keystream (XOR of the two plaintexts) and enables forgery of the authentication tag. This is the single most common fatal bug in application GCM code.

- Anti-pattern: a fixed/constant IV (`Buffer.alloc(12)`, a hardcoded literal, an IV derived from a counter that resets, or an IV reused across messages); an IV shorter/longer than 12 bytes without deliberate reason.
- Anti-pattern: storing only the ciphertext and discarding the auth tag, or never calling `getAuthTag()` / `setAuthTag()` (unauthenticated decryption silently accepts tampered input).
- Fix: generate a fresh 12-byte (96-bit) IV per message with `crypto.randomBytes(12)`; NIST SP 800-38D recommends restricting GCM IVs to 96 bits for efficiency and interoperability (other lengths are permitted but get hashed internally). Persist `iv || authTag || ciphertext` together.
- Fix: on encrypt call `cipher.getAuthTag()` after `cipher.final()`; on decrypt call `decipher.setAuthTag(tag)` before `decipher.final()`. A wrong/absent tag must make `final()` throw and abort — do not swallow it.
- Note: GCM's 96-bit nonce space makes random-nonce collisions non-negligible past very high message volumes under one key; for high-volume or long-lived keys prefer XChaCha20-Poly1305 (192-bit nonce, `crypto_aead_xchacha20poly1305_ietf_NPUBBYTES` = 24) whose extended nonce makes random nonces safe, or rotate keys. Verify constant names/nonce lengths against the installed Node/libsodium version.

## Randomness: CSPRNG for every key, IV, salt, and token

Any key, IV/nonce, salt, or unguessable token derived from a non-cryptographic RNG is predictable and defeats the cipher.

- Anti-pattern: `Math.random()`, `Date.now()`, `process.hrtime()`, PID, or an incrementing counter used to produce a key, IV, salt, session id, reset token, or API key.
- Fix: Node `crypto.randomBytes(n)` (or `crypto.randomFillSync`), `crypto.randomUUID()` for opaque ids; browser/WebCrypto `crypto.getRandomValues(new Uint8Array(n))`. Never `Math.random()` for anything security-relevant.

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
