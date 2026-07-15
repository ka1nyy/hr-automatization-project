"""Sensitive-field encryption adapter.

The key must come from the runtime secret store. Ciphertext is versioned so keys can be
rotated without changing the domain contract.
"""

from cryptography.fernet import Fernet, InvalidToken

from ..domain.errors import EmployeeDomainError


class FernetSensitiveDataProtector:
    def __init__(self, key: str) -> None:
        if not key:
            raise ValueError("A sensitive-data encryption key is required.")
        self._fernet = Fernet(key.encode("ascii"))

    def protect(self, value: str) -> bytes:
        return b"v1:" + self._fernet.encrypt(value.encode("utf-8"))

    def reveal(self, value: bytes) -> str:
        if not value.startswith(b"v1:"):
            raise EmployeeDomainError(
                "VALIDATION_FAILED", "Unsupported sensitive-data format.", {}, 500
            )
        try:
            return self._fernet.decrypt(value[3:]).decode("utf-8")
        except InvalidToken as exc:
            raise EmployeeDomainError(
                "VALIDATION_FAILED", "Sensitive data could not be decrypted.", {}, 500
            ) from exc
