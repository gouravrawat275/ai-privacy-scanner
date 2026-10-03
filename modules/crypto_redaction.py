"""
Aspect D — Cryptographically Reversible Redaction

Reversibly and cryptographically obscures flagged regions of an image such that
the original content can be restored only by an authorized key or passphrase holder.

Security Architecture:
- Obscures sensitive regions in the pixel buffer (heavy blur or pixelation).
- Serializes and compresses the pristine original pixel patches.
- Encrypts the patch package using AES-256-GCM (Authenticated Encryption with Associated Data).
- Key derivation via PBKDF2-HMAC-SHA256 (100,000 rounds) or direct 256-bit AES key.
- Embeds encrypted payload in PNG metadata or exports standalone authenticated .privpack envelopes.
- Restoration verifies ciphertext integrity before injecting pixels back into coordinates.
"""

import os
import json
import base64
import zlib
import secrets
from typing import Dict, List, Any, Optional, Tuple, Union
import cv2
import numpy as np
from PIL import Image, PngImagePlugin
import io

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend


PNG_METADATA_KEY = "PrivacyLockPayload"
MAGIC_HEADER = "PRIVACY_LOCK_V1"
STEGO_MAGIC = b"PLSTEG01"


class CryptoRedactor:
    """
    Manages reversible cryptographic obscuration and decryption restoration of images.
    """

    def __init__(self):
        pass

    @staticmethod
    def generate_random_key() -> str:
        """Generate a cryptographically secure 256-bit key in Base64 format."""
        raw_key = AESGCM.generate_key(bit_length=256)
        return base64.b64encode(raw_key).decode('utf-8')

    @staticmethod
    def derive_key_from_password(password: str, salt: bytes) -> bytes:
        """Derive a 256-bit AES key from a human passphrase using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(password.encode('utf-8'))

    def obscure_and_encrypt(
        self,
        image_bgr: np.ndarray,
        regions: List[Dict[str, Any]],
        passphrase: Optional[str] = None,
        raw_key_b64: Optional[str] = None,
        blur_style: str = 'pixelate'  # 'pixelate', 'blur', 'blackout'
    ) -> Dict[str, Any]:
        """
        Obscure flagged regions in image and encrypt original pixel data.

        regions: List of dicts with 'bbox': [x, y, w, h] and optional 'type', 'label'
        Returns:
            {
                'obscured_image_bgr': np.ndarray,
                'encrypted_envelope': dict,
                'key_b64': str,  # only returned if raw key was generated
                'salt_b64': str,
                'regions_count': int
            }
        """
        if not passphrase and not raw_key_b64:
            # Generate random 256-bit key
            raw_key = AESGCM.generate_key(bit_length=256)
            salt = secrets.token_bytes(16)
            key_b64_out = base64.b64encode(raw_key).decode('utf-8')
        elif passphrase:
            salt = secrets.token_bytes(16)
            raw_key = self.derive_key_from_password(passphrase, salt)
            key_b64_out = None
        else:
            raw_key = base64.b64decode(raw_key_b64.encode('utf-8'))
            salt = secrets.token_bytes(16)
            key_b64_out = raw_key_b64

        obscured_img = image_bgr.copy()
        img_h, img_w = image_bgr.shape[:2]

        patches_data = []

        for idx, reg in enumerate(regions):
            bbox = reg.get('bbox')
            if not bbox or len(bbox) < 4:
                continue

            x, y, w, h = [int(v) for v in bbox]
            x1 = max(0, x)
            y1 = max(0, y)
            x2 = min(img_w, x + w)
            y2 = min(img_h, y + h)

            if x2 <= x1 or y2 <= y1:
                continue

            # 1. Harvest original patch
            patch = image_bgr[y1:y2, x1:x2].copy()
            # Compress patch bytes with zlib
            compressed_patch = zlib.compress(patch.tobytes(), level=6)
            patch_entry = {
                'id': idx,
                'bbox': [x1, y1, x2 - x1, y2 - y1],
                'shape': list(patch.shape),
                'dtype': str(patch.dtype),
                'type': reg.get('type', 'redacted'),
                'label': reg.get('label', ''),
                'patch_data_b64': base64.b64encode(compressed_patch).decode('utf-8')
            }
            patches_data.append(patch_entry)

            # 2. Obscure patch in obscured_img
            target_slice = obscured_img[y1:y2, x1:x2]
            pw, ph = x2 - x1, y2 - y1

            if blur_style in ('blackout', 'solid_tile'):
                target_slice[:] = (45, 52, 54) if blur_style == 'solid_tile' else 0
            elif blur_style == 'neutral_placeholder':
                # Visually neutral opaque placeholder tile with zero statistical recovery
                target_slice[:] = (60, 63, 65)
                # Draw subtle decorative grid/crosshatch pattern
                step = max(8, min(pw, ph) // 6)
                for gx in range(0, pw, step):
                    cv2.line(target_slice, (gx, 0), (gx, ph), (75, 78, 80), 1)
                for gy in range(0, ph, step):
                    cv2.line(target_slice, (0, gy), (pw, gy), (75, 78, 80), 1)
                # Outer border
                cv2.rectangle(target_slice, (0, 0), (pw - 1, ph - 1), (100, 110, 120), 1)
            elif blur_style == 'pixelate':
                # Downsample and upsample
                pixel_size = max(4, min(pw, ph) // 10)
                small_w = max(1, pw // pixel_size)
                small_h = max(1, ph // pixel_size)
                small = cv2.resize(target_slice, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
                pixelated = cv2.resize(small, (pw, ph), interpolation=cv2.INTER_NEAREST)
                obscured_img[y1:y2, x1:x2] = pixelated
            else:  # 'blur'
                k_w = max(15, (pw // 5) * 2 + 1)
                k_h = max(15, (ph // 5) * 2 + 1)
                blurred = cv2.GaussianBlur(target_slice, (k_w, k_h), 0)
                obscured_img[y1:y2, x1:x2] = blurred

        # 3. Encrypt patches payload using AES-256-GCM
        payload_bytes = json.dumps({
            'magic': MAGIC_HEADER,
            'image_shape': list(image_bgr.shape),
            'patches': patches_data
        }).encode('utf-8')

        nonce = secrets.token_bytes(12)  # 96-bit nonce for AESGCM
        aesgcm = AESGCM(raw_key)
        ciphertext = aesgcm.encrypt(nonce, payload_bytes, associated_data=MAGIC_HEADER.encode('utf-8'))

        envelope = {
            'format': MAGIC_HEADER,
            'salt_b64': base64.b64encode(salt).decode('utf-8'),
            'nonce_b64': base64.b64encode(nonce).decode('utf-8'),
            'ciphertext_b64': base64.b64encode(ciphertext).decode('utf-8'),
            'patches_count': len(patches_data)
        }

        return {
            'obscured_image_bgr': obscured_img,
            'encrypted_envelope': envelope,
            'key_b64': key_b64_out,
            'salt_b64': envelope['salt_b64'],
            'regions_count': len(patches_data)
        }

    def decrypt_and_restore(
        self,
        obscured_image_bgr: np.ndarray,
        envelope: Dict[str, Any],
        passphrase: Optional[str] = None,
        raw_key_b64: Optional[str] = None
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        Decrypt encrypted envelope and restore original pixels.

        Returns: (success: bool, restored_image_bgr: Optional[np.ndarray], message: str)
        """
        try:
            salt = base64.b64decode(envelope['salt_b64'])
            nonce = base64.b64decode(envelope['nonce_b64'])
            ciphertext = base64.b64decode(envelope['ciphertext_b64'])

            if passphrase:
                key = self.derive_key_from_password(passphrase, salt)
            elif raw_key_b64:
                key = base64.b64decode(raw_key_b64.encode('utf-8'))
            else:
                return False, None, "Neither passphrase nor secret key was provided."

            aesgcm = AESGCM(key)
            decrypted_bytes = aesgcm.decrypt(
                nonce,
                ciphertext,
                associated_data=MAGIC_HEADER.encode('utf-8')
            )
            payload = json.loads(decrypted_bytes.decode('utf-8'))

            if payload.get('magic') != MAGIC_HEADER:
                return False, None, "Invalid payload header or corrupted data."

            restored_bgr = obscured_image_bgr.copy()
            patches = payload.get('patches', [])

            for p in patches:
                x, y, w, h = p['bbox']
                shape = tuple(p['shape'])
                dtype = np.dtype(p['dtype'])
                compressed = base64.b64decode(p['patch_data_b64'])
                raw_patch_bytes = zlib.decompress(compressed)
                patch = np.frombuffer(raw_patch_bytes, dtype=dtype).reshape(shape)

                # Inject back
                restored_bgr[y:y+h, x:x+w] = patch

            return True, restored_bgr, f"Successfully restored {len(patches)} obscured regions."

        except Exception as e:
            return False, None, f"Decryption failed: Incorrect passphrase/key or tampered data ({e})."

    def embed_steganographic(
        self,
        obscured_image_bgr: np.ndarray,
        envelope: Dict[str, Any]
    ) -> np.ndarray:
        """
        Aspect D (Patent Claim D3): Embed encrypted envelope directly into the image
        pixel LSBs so that a single image file both displays the visually neutral placeholder
        and carries the payload necessary for an authorized recipient to recover the flagged region.
        """
        envelope_bytes = json.dumps(envelope).encode('utf-8')
        compressed = zlib.compress(envelope_bytes, level=9)
        length_prefix = len(compressed).to_bytes(4, byteorder='big')
        full_data = STEGO_MAGIC + length_prefix + compressed

        h, w, c = obscured_image_bgr.shape
        total_bits = h * w * c
        required_bits = len(full_data) * 8
        if required_bits > total_bits:
            raise ValueError(
                f"Image capacity ({total_bits} bits) insufficient for steganographic payload ({required_bits} bits). "
                "Use standard metadata encapsulation or a higher resolution frame."
            )

        flat = obscured_image_bgr.copy().reshape(-1)
        bits = np.unpackbits(np.frombuffer(full_data, dtype=np.uint8))
        flat[:len(bits)] = (flat[:len(bits)] & 0xFE) | bits
        return flat.reshape(obscured_image_bgr.shape)

    def extract_steganographic(
        self,
        image_bgr: np.ndarray
    ) -> Optional[Dict[str, Any]]:
        """
        Aspect D (Patent Claim D3): Extract encrypted envelope from pixel LSBs.
        """
        try:
            flat = image_bgr.reshape(-1)
            if len(flat) < 96:
                return None
            header_bits = flat[:96] & 1
            header_bytes = np.packbits(header_bits).tobytes()
            if header_bytes[:8] != STEGO_MAGIC:
                return None
            length = int.from_bytes(header_bytes[8:12], byteorder='big')
            total_payload_bits = 96 + length * 8
            if total_payload_bits > len(flat):
                return None
            payload_bits = flat[96:total_payload_bits] & 1
            compressed = np.packbits(payload_bits).tobytes()
            envelope_json = zlib.decompress(compressed).decode('utf-8')
            return json.loads(envelope_json)
        except Exception:
            return None

    def export_embedded_png(
        self,
        obscured_image_bgr: np.ndarray,
        envelope: Dict[str, Any],
        use_steganography: bool = False
    ) -> bytes:
        """
        Export obscured image as PNG with the encrypted envelope embedded in
        PNG metadata chunk (default, 100% bit-exact background) or
        steganographic pixel LSBs (Patent Claim D3).
        """
        export_img = obscured_image_bgr
        if use_steganography:
            try:
                export_img = self.embed_steganographic(obscured_image_bgr, envelope)
            except Exception:
                # Fallback to PNG metadata chunk if capacity exceeded
                pass

        rgb = cv2.cvtColor(export_img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)

        meta = PngImagePlugin.PngInfo()
        meta.add_text(PNG_METADATA_KEY, json.dumps(envelope))

        buf = io.BytesIO()
        pil_img.save(buf, format="PNG", pnginfo=meta)
        return buf.getvalue()

    def export_steganographic_png(
        self,
        obscured_image_bgr: np.ndarray,
        envelope: Dict[str, Any]
    ) -> bytes:
        """
        Aspect D (Patent Claim D3): Explicitly export obscured image with the encrypted
        envelope embedded using steganography in pixel LSBs.
        """
        return self.export_embedded_png(obscured_image_bgr, envelope, use_steganography=True)

    def load_embedded_png(
        self,
        png_bytes: bytes
    ) -> Tuple[np.ndarray, Optional[Dict[str, Any]]]:
        """
        Read an image and extract embedded PrivacyLock payload if present,
        checking both PNG metadata chunks and steganographic pixel LSBs.
        """
        pil_img = Image.open(io.BytesIO(png_bytes))
        rgb = np.array(pil_img.convert("RGB"))
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        envelope = None
        # 1. Try PNG metadata text chunk
        if hasattr(pil_img, 'text') and PNG_METADATA_KEY in pil_img.text:
            try:
                envelope = json.loads(pil_img.text[PNG_METADATA_KEY])
            except Exception:
                envelope = None

        # 2. Try steganographic extraction if metadata is absent/stripped
        if envelope is None:
            envelope = self.extract_steganographic(bgr)

        return bgr, envelope
