"""Make the VAPID key pair for leftover-food alerts (web push). Run once:

    python scripts/generate_vapid_keys.py

Then add both lines to the backend's environment (for example `vercel env add VAPID_PUBLIC_KEY
production`, then the same for VAPID_PRIVATE_KEY) and redeploy. Keep the private key secret.
Changing the keys later means every customer has to turn alerts on again.
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


key = ec.generate_private_key(ec.SECP256R1())
private = key.private_numbers().private_value.to_bytes(32, "big")
public = key.public_key().public_bytes(
    serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
)
print(f"VAPID_PUBLIC_KEY={b64url(public)}")
print(f"VAPID_PRIVATE_KEY={b64url(private)}")
