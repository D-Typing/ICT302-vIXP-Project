from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import ParticipantRegistration, User
from .validators import validate_private_asn


FORM_CONTROL_CLASS = (
    "w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 "
    "text-white placeholder-gray-500 text-sm focus:outline-none focus:border-blue-500 transition"
)
MONO_FORM_CONTROL_CLASS = f"{FORM_CONTROL_CLASS} font-mono"
CHECKBOX_CLASS = "w-4 h-4 accent-blue-500"


class PublicRegistrationForm(forms.Form):
    first_name = forms.CharField(
        max_length=150,
        label="First Name",
        widget=forms.TextInput(attrs={"class": FORM_CONTROL_CLASS, "placeholder": "Declan"}),
    )
    last_name = forms.CharField(
        max_length=150,
        label="Last Name",
        widget=forms.TextInput(attrs={"class": FORM_CONTROL_CLASS, "placeholder": "Smith"}),
    )
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"class": FORM_CONTROL_CLASS, "placeholder": "declan@example.edu"}),
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": FORM_CONTROL_CLASS, "autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={"class": FORM_CONTROL_CLASS, "autocomplete": "new-password"}),
    )
    organisation_name = forms.CharField(
        max_length=255,
        label="Organisation Name",
        widget=forms.TextInput(attrs={"class": FORM_CONTROL_CLASS, "placeholder": "Acme Networks Pty Ltd"}),
    )
    asn = forms.CharField(
        label="AS Number (ASN)",
        help_text="Private ASN only: 64512-65534 or 4200000000-4294967294.",
        widget=forms.TextInput(
            attrs={
                "class": MONO_FORM_CONTROL_CLASS,
                "placeholder": "AS65000",
                "inputmode": "numeric",
            }
        ),
    )
    ipv4_peering_address = forms.GenericIPAddressField(
        protocol="IPv4",
        required=False,
        label="IPv4 Peering Address",
        widget=forms.TextInput(attrs={"class": MONO_FORM_CONTROL_CLASS, "placeholder": "192.0.2.1"}),
    )
    ipv6_peering_address = forms.GenericIPAddressField(
        protocol="IPv6",
        required=False,
        label="IPv6 Peering Address",
        widget=forms.TextInput(attrs={"class": MONO_FORM_CONTROL_CLASS, "placeholder": "2001:db8::1"}),
    )
    max_prefix_v4 = forms.IntegerField(
        min_value=1,
        initial=100,
        label="Max Prefixes (IPv4)",
        widget=forms.NumberInput(attrs={"class": FORM_CONTROL_CLASS, "placeholder": "100", "min": 1}),
    )
    max_prefix_v6 = forms.IntegerField(
        min_value=1,
        initial=50,
        label="Max Prefixes (IPv6)",
        widget=forms.NumberInput(attrs={"class": FORM_CONTROL_CLASS, "placeholder": "50", "min": 1}),
    )
    peeringdb_url = forms.URLField(
        required=False,
        label="PeeringDB URL",
        widget=forms.URLInput(
            attrs={"class": FORM_CONTROL_CLASS, "placeholder": "https://www.peeringdb.com/net/12345"}
        ),
    )
    connect_rs1 = forms.BooleanField(
        required=False,
        initial=True,
        label="Connect to Route Server 1 (RS1)",
        widget=forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
    )
    connect_rs2 = forms.BooleanField(
        required=False,
        initial=False,
        label="Connect to Route Server 2 (RS2)",
        widget=forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean_asn(self):
        raw_asn = self.cleaned_data["asn"]
        normalized_asn = raw_asn.strip().upper().removeprefix("AS")

        try:
            asn = int(normalized_asn)
        except ValueError:
            raise ValidationError("ASN must be a whole number.")

        validate_private_asn(asn)
        if ParticipantRegistration.objects.filter(asn=asn).exists():
            raise ValidationError("This ASN has already been registered.")
        return asn

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords do not match.")

        if password1:
            try:
                validate_password(password1)
            except ValidationError as error:
                self.add_error("password1", error)

        return cleaned_data

    def participant_data(self):
        return {
            "organisation_name": self.cleaned_data["organisation_name"],
            "asn": self.cleaned_data["asn"],
            "ipv4_peering_address": self.cleaned_data.get("ipv4_peering_address") or None,
            "ipv6_peering_address": self.cleaned_data.get("ipv6_peering_address") or None,
            "max_prefix_v4": self.cleaned_data["max_prefix_v4"],
            "max_prefix_v6": self.cleaned_data["max_prefix_v6"],
            "peeringdb_url": self.cleaned_data.get("peeringdb_url") or None,
            "connect_rs1": self.cleaned_data["connect_rs1"],
            "connect_rs2": self.cleaned_data["connect_rs2"],
            "status": ParticipantRegistration.Status.PENDING,
        }


class ParticipantRegistrationForm(forms.ModelForm):

    class Meta:
        model = ParticipantRegistration
        fields = [
            "organisation_name",
            "asn",
            "ipv4_peering_address",
            "ipv6_peering_address",
            "max_prefix_v4",
            "max_prefix_v6",
            "peeringdb_url",
            "connect_rs1",
            "connect_rs2",
        ]
        labels = {
            "organisation_name": "Organisation Name",
            "ipv4_peering_address": "IPv4 Peering Address",
            "ipv6_peering_address": "IPv6 Peering Address",
            "max_prefix_v4": "Max Prefixes (IPv4)",
            "max_prefix_v6": "Max Prefixes (IPv6)",
            "peeringdb_url": "PeeringDB URL",
            "connect_rs1": "Connect to Route Server 1 (RS1)",
            "connect_rs2": "Connect to Route Server 2 (RS2)",
        }
        widgets = {
            "organisation_name": forms.TextInput(
                attrs={
                    "class": FORM_CONTROL_CLASS,
                    "placeholder": "Acme Networks Pty Ltd",
                }
            ),
            "ipv4_peering_address": forms.TextInput(
                attrs={
                    "class": MONO_FORM_CONTROL_CLASS,
                    "placeholder": "192.0.2.1",
                }
            ),
            "ipv6_peering_address": forms.TextInput(
                attrs={
                    "class": MONO_FORM_CONTROL_CLASS,
                    "placeholder": "2001:db8::1",
                }
            ),
            "max_prefix_v4": forms.NumberInput(
                attrs={
                    "class": FORM_CONTROL_CLASS,
                    "placeholder": "100",
                    "min": 1,
                }
            ),
            "max_prefix_v6": forms.NumberInput(
                attrs={
                    "class": FORM_CONTROL_CLASS,
                    "placeholder": "50",
                    "min": 1,
                }
            ),
            "peeringdb_url": forms.URLInput(
                attrs={
                    "class": FORM_CONTROL_CLASS,
                    "placeholder": "https://www.peeringdb.com/net/12345",
                }
            ),
            "connect_rs1": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
            "connect_rs2": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
        }

    def clean_asn(self):
        raw_asn = self.cleaned_data["asn"]
        normalized_asn = raw_asn.strip().upper().removeprefix("AS")

        try:
            asn = int(normalized_asn)
        except ValueError:
            raise ValidationError("ASN must be a whole number.")

        validate_private_asn(asn)
        return asn
