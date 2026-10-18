"""Fixtures partagées par les tests du banc."""

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


@pytest.fixture(scope="module")
def cle_adc() -> str:
    """Clé privée d'un compte de service factice : l'ADC de Vertex, signée puis échangée contre un
    jeton auprès de la fausse API (token_uri) ; une ADC d'utilisateur irait au vrai point de
    Google."""
    cle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = cle.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return pem.decode()
