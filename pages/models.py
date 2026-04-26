from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .validators import validate_ip_prefix, validate_private_asn, validate_wireguard_public_key


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", _("Admin")
        PARTICIPANT = "participant", _("Participant")

    email = models.EmailField(_("email address"), unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PARTICIPANT)
    phone_number = models.CharField(max_length=32, blank=True, null=True)
    email_verified = models.BooleanField(default=False)

    class Meta:
        ordering = ["username"]
        indexes = [
            models.Index(fields=["email"], name="user_email_idx"),
            models.Index(fields=["role"], name="user_role_idx"),
        ]
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self):
        return self.get_full_name() or self.username


class ParticipantRegistration(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        SUSPENDED = "suspended", _("Suspended")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="participant_registration",
    )
    organisation_name = models.CharField(max_length=255)
    asn = models.PositiveBigIntegerField(
        unique=True,
        validators=[validate_private_asn],
        verbose_name="AS number",
    )
    ipv4_peering_address = models.GenericIPAddressField(
        protocol="IPv4",
        blank=True,
        null=True,
        verbose_name="IPv4 peering address",
    )
    ipv6_peering_address = models.GenericIPAddressField(
        protocol="IPv6",
        blank=True,
        null=True,
        verbose_name="IPv6 peering address",
    )
    max_prefix_v4 = models.PositiveIntegerField(
        default=100,
        validators=[MinValueValidator(1)],
        verbose_name="maximum IPv4 prefixes",
    )
    max_prefix_v6 = models.PositiveIntegerField(
        default=50,
        validators=[MinValueValidator(1)],
        verbose_name="maximum IPv6 prefixes",
    )
    peeringdb_url = models.URLField(blank=True, null=True, verbose_name="PeeringDB URL")
    connect_rs1 = models.BooleanField(default=True, verbose_name="connect to route server 1")
    connect_rs2 = models.BooleanField(default=False, verbose_name="connect to route server 2")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="reviewed_participant_registrations",
    )
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(asn__gte=64512, asn__lte=65534)
                    | Q(asn__gte=4200000000, asn__lte=4294967294)
                ),
                name="participant_private_asn_range",
            ),
            models.CheckConstraint(
                condition=Q(max_prefix_v4__gte=1),
                name="participant_max_pfx4_positive",
            ),
            models.CheckConstraint(
                condition=Q(max_prefix_v6__gte=1),
                name="participant_max_pfx6_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["organisation_name"], name="participant_org_idx"),
            models.Index(fields=["status"], name="participant_status_idx"),
            models.Index(fields=["status", "submitted_at"], name="participant_status_sub_idx"),
        ]
        verbose_name = "participant registration"
        verbose_name_plural = "participant registrations"

    def __str__(self):
        return f"{self.organisation_name} (AS{self.asn})"

    def mark_reviewed(self, reviewer, status):
        self.status = status
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "reviewed_by", "reviewed_at"])


class PrefixRegistration(models.Model):
    class IPVersion(models.TextChoices):
        IPV4 = "IPv4", _("IPv4")
        IPV6 = "IPv6", _("IPv6")

    participant = models.ForeignKey(
        ParticipantRegistration,
        on_delete=models.CASCADE,
        related_name="prefix_registrations",
    )
    prefix = models.CharField(max_length=43, validators=[validate_ip_prefix])
    ip_version = models.CharField(max_length=4, choices=IPVersion.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["participant", "ip_version", "prefix"]
        constraints = [
            models.UniqueConstraint(fields=["participant", "prefix"], name="unique_participant_prefix"),
        ]
        indexes = [
            models.Index(fields=["participant", "ip_version"], name="prefix_participant_version_idx"),
            models.Index(fields=["is_active"], name="prefix_active_idx"),
        ]
        verbose_name = "prefix registration"
        verbose_name_plural = "prefix registrations"

    def clean(self):
        super().clean()
        validate_ip_prefix(self.prefix, expected_version=self.ip_version)

    def __str__(self):
        return f"{self.participant} - {self.prefix}"


class VPNAssignment(models.Model):
    participant = models.OneToOneField(
        ParticipantRegistration,
        on_delete=models.CASCADE,
        related_name="vpn_assignment",
    )
    vpn_ipv4 = models.GenericIPAddressField(protocol="IPv4", unique=True, verbose_name="VPN IPv4 address")
    vpn_ipv6 = models.GenericIPAddressField(
        protocol="IPv6",
        unique=True,
        blank=True,
        null=True,
        verbose_name="VPN IPv6 address",
    )
    wireguard_public_key = models.CharField(
        max_length=88,
        validators=[validate_wireguard_public_key],
        blank=True,
        null=True,
    )
    config_generated = models.BooleanField(default=False)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assigned_at"]
        indexes = [
            models.Index(fields=["config_generated"], name="vpn_config_generated_idx"),
        ]
        verbose_name = "VPN assignment"
        verbose_name_plural = "VPN assignments"

    def __str__(self):
        return f"{self.participant} - {self.vpn_ipv4}"


class BGPSessionStatus(models.Model):
    class RouteServer(models.TextChoices):
        RS1 = "RS1", _("Route Server 1")
        RS2 = "RS2", _("Route Server 2")

    class SessionState(models.TextChoices):
        IDLE = "Idle", _("Idle")
        CONNECT = "Connect", _("Connect")
        ACTIVE = "Active", _("Active")
        OPENSENT = "OpenSent", _("OpenSent")
        OPENCONFIRM = "OpenConfirm", _("OpenConfirm")
        ESTABLISHED = "Established", _("Established")

    participant = models.ForeignKey(
        ParticipantRegistration,
        on_delete=models.CASCADE,
        related_name="bgp_session_statuses",
    )
    route_server = models.CharField(max_length=3, choices=RouteServer.choices)
    session_state = models.CharField(max_length=20, choices=SessionState.choices, default=SessionState.IDLE)
    last_seen = models.DateTimeField(default=timezone.now, db_index=True)
    prefixes_received = models.PositiveIntegerField(default=0)
    prefixes_advertised = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["participant", "route_server"]
        constraints = [
            models.UniqueConstraint(fields=["participant", "route_server"], name="unique_participant_rs"),
        ]
        indexes = [
            models.Index(fields=["route_server", "session_state"], name="bgp_route_server_state_idx"),
            models.Index(fields=["participant", "last_seen"], name="bgp_participant_last_seen_idx"),
        ]
        verbose_name = "BGP session status"
        verbose_name_plural = "BGP session statuses"

    def __str__(self):
        return f"{self.participant} {self.route_server}: {self.session_state}"
