from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone

from .models import BGPSessionStatus, ParticipantRegistration, PrefixRegistration, User, VPNAssignment


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff", "is_active")
    list_filter = ("role", "email_verified", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)

    fieldsets = UserAdmin.fieldsets + (
        ("vIXP profile", {"fields": ("role", "phone_number", "email_verified")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("vIXP profile", {"fields": ("email", "role", "phone_number", "email_verified")}),
    )


class PrefixRegistrationInline(admin.TabularInline):
    model = PrefixRegistration
    extra = 0
    fields = ("prefix", "ip_version", "is_active", "created_at")
    readonly_fields = ("created_at",)


class VPNAssignmentInline(admin.StackedInline):
    model = VPNAssignment
    extra = 0
    max_num = 1


class BGPSessionStatusInline(admin.TabularInline):
    model = BGPSessionStatus
    extra = 0
    fields = ("route_server", "session_state", "last_seen", "prefixes_received", "prefixes_advertised")


@admin.register(ParticipantRegistration)
class ParticipantRegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "organisation_name",
        "asn",
        "status",
        "connect_rs1",
        "connect_rs2",
        "submitted_at",
        "reviewed_at",
    )
    list_filter = ("status", "connect_rs1", "connect_rs2", "submitted_at")
    search_fields = ("organisation_name", "asn", "user__username", "user__email")
    readonly_fields = ("submitted_at", "reviewed_at", "reviewed_by")
    autocomplete_fields = ("user", "reviewed_by")
    ordering = ("-submitted_at",)
    actions = ("approve_registrations", "reject_registrations", "suspend_registrations")
    inlines = (PrefixRegistrationInline, VPNAssignmentInline, BGPSessionStatusInline)

    fieldsets = (
        ("Participant", {"fields": ("user", "organisation_name", "asn", "status")}),
        (
            "Peering details",
            {
                "fields": (
                    "ipv4_peering_address",
                    "ipv6_peering_address",
                    "max_prefix_v4",
                    "max_prefix_v6",
                    "peeringdb_url",
                    "connect_rs1",
                    "connect_rs2",
                )
            },
        ),
        ("Review", {"fields": ("submitted_at", "reviewed_at", "reviewed_by", "notes")}),
    )

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data and obj.status != ParticipantRegistration.Status.PENDING:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)
        self._sync_user_status(obj)

    @admin.action(description="Approve selected participant registrations")
    def approve_registrations(self, request, queryset):
        self._mark_reviewed(request, queryset, ParticipantRegistration.Status.APPROVED)

    @admin.action(description="Reject selected participant registrations")
    def reject_registrations(self, request, queryset):
        self._mark_reviewed(request, queryset, ParticipantRegistration.Status.REJECTED)

    @admin.action(description="Suspend selected participant registrations")
    def suspend_registrations(self, request, queryset):
        self._mark_reviewed(request, queryset, ParticipantRegistration.Status.SUSPENDED)

    def _mark_reviewed(self, request, queryset, status):
        reviewed_at = timezone.now()
        updated = queryset.update(status=status, reviewed_by=request.user, reviewed_at=reviewed_at)

        user_ids = queryset.values_list("user_id", flat=True)
        if status == ParticipantRegistration.Status.APPROVED:
            User.objects.filter(id__in=user_ids).update(is_active=True)
        elif status in {ParticipantRegistration.Status.REJECTED, ParticipantRegistration.Status.SUSPENDED}:
            User.objects.filter(id__in=user_ids).update(is_active=False)

        self.message_user(request, f"{updated} registration(s) marked as {status}.", messages.SUCCESS)

    def _sync_user_status(self, registration):
        if registration.status == ParticipantRegistration.Status.APPROVED and not registration.user.is_active:
            registration.user.is_active = True
            registration.user.save(update_fields=["is_active"])
        elif (
            registration.status in {ParticipantRegistration.Status.REJECTED, ParticipantRegistration.Status.SUSPENDED}
            and registration.user.is_active
        ):
            registration.user.is_active = False
            registration.user.save(update_fields=["is_active"])


@admin.register(PrefixRegistration)
class PrefixRegistrationAdmin(admin.ModelAdmin):
    list_display = ("participant", "prefix", "ip_version", "is_active", "created_at")
    list_filter = ("ip_version", "is_active", "created_at")
    search_fields = ("participant__organisation_name", "participant__asn", "prefix")
    autocomplete_fields = ("participant",)
    ordering = ("participant", "ip_version", "prefix")


@admin.register(VPNAssignment)
class VPNAssignmentAdmin(admin.ModelAdmin):
    list_display = ("participant", "vpn_ipv4", "vpn_ipv6", "config_generated", "assigned_at")
    list_filter = ("config_generated", "assigned_at")
    search_fields = ("participant__organisation_name", "participant__asn", "vpn_ipv4", "vpn_ipv6")
    autocomplete_fields = ("participant",)
    ordering = ("-assigned_at",)


@admin.register(BGPSessionStatus)
class BGPSessionStatusAdmin(admin.ModelAdmin):
    list_display = (
        "participant",
        "route_server",
        "session_state",
        "last_seen",
        "prefixes_received",
        "prefixes_advertised",
    )
    list_filter = ("route_server", "session_state", "last_seen")
    search_fields = ("participant__organisation_name", "participant__asn")
    autocomplete_fields = ("participant",)
    ordering = ("participant", "route_server")
