import base64
import ipaddress

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


PRIVATE_ASN_RANGES = (
    (64512, 65534),
    (4200000000, 4294967294),
)


def validate_private_asn(value):
    if isinstance(value, str):
        value = value.strip().upper().removeprefix("AS")

    try:
        asn = int(value)
    except (TypeError, ValueError):
        raise ValidationError(_("ASN must be a whole number."), code="invalid_asn")

    if any(start <= asn <= end for start, end in PRIVATE_ASN_RANGES):
        return

    raise ValidationError(
        _("ASN must be in a private range: 64512-65534 or 4200000000-4294967294."),
        code="invalid_private_asn",
    )


def validate_ip_prefix(value, expected_version=None):
    try:
        network = ipaddress.ip_network(value, strict=True)
    except (TypeError, ValueError):
        raise ValidationError(_("Prefix must be a valid IPv4 or IPv6 CIDR network."), code="invalid_prefix")

    if expected_version == "IPv4" and network.version != 4:
        raise ValidationError(_("Prefix must be an IPv4 CIDR network."), code="invalid_ipv4_prefix")

    if expected_version == "IPv6" and network.version != 6:
        raise ValidationError(_("Prefix must be an IPv6 CIDR network."), code="invalid_ipv6_prefix")


def validate_wireguard_public_key(value):
    if value in (None, ""):
        return

    try:
        decoded = base64.b64decode(value, validate=True)
    except Exception:
        raise ValidationError(_("WireGuard public key must be valid base64."), code="invalid_wireguard_key")

    if len(decoded) != 32:
        raise ValidationError(_("WireGuard public key must decode to 32 bytes."), code="invalid_wireguard_key")
