from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render

from .forms import PublicRegistrationForm
from .models import (
    ParticipantRegistration,
    User,
    BGPSessionStatus,
    PrefixFilter,
    PeeringSession,
)


@login_required
def dashboard(request):
    sessions = BGPSessionStatus.objects.select_related('participant').all()
    established = sessions.filter(session_state=BGPSessionStatus.SessionState.ESTABLISHED)
    global_filters = PrefixFilter.objects.filter(participant=None)

    context = {
        'sessions': sessions,
        'established_count': established.count(),
        'idle_count': sessions.exclude(
            session_state=BGPSessionStatus.SessionState.ESTABLISHED
        ).count(),
        'total_peers': ParticipantRegistration.objects.filter(
            status=ParticipantRegistration.Status.APPROVED
        ).count(),
        'total_prefixes_received': sum(s.prefixes_received for s in established),
        'total_prefixes_advertised': sum(s.prefixes_advertised for s in established),
        'ipv4_received': sum(s.prefixes_received for s in established.filter(family='ipv4')),
        'ipv6_received': sum(s.prefixes_received for s in established.filter(family='ipv6')),
        'ipv4_advertised': sum(s.prefixes_advertised for s in established.filter(family='ipv4')),
        'ipv6_advertised': sum(s.prefixes_advertised for s in established.filter(family='ipv6')),
        'prefix_filters': global_filters,
    }
    return render(request, 'pages/dashboard.html', context)


def register(request):
    if request.method == 'POST':
        form = PublicRegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=form.cleaned_data['email'],
                        email=form.cleaned_data['email'],
                        password=form.cleaned_data['password1'],
                        first_name=form.cleaned_data['first_name'],
                        last_name=form.cleaned_data['last_name'],
                        role=User.Role.PARTICIPANT,
                        is_active=False,
                        email_verified=False,
                    )
                    ParticipantRegistration.objects.create(user=user, **form.participant_data())
            except IntegrityError:
                form.add_error(None, 'A registration already exists for this email or ASN.')
            else:
                messages.success(request, 'Application submitted. Await admin approval.')
                return redirect('login')
    else:
        form = PublicRegistrationForm()

    return render(request, 'pages/register.html', {'form': form})


def documentation(request):
    return render(request, 'pages/documentation.html')


@login_required
def peer_matrix(request):
    participants = ParticipantRegistration.objects.filter(
        status=ParticipantRegistration.Status.APPROVED
    ).order_by('asn')

    # Use "asn_a,asn_b" string keys instead of tuples
    peering_map = {}
    for ps in PeeringSession.objects.select_related('member_a', 'member_b'):
        key_ab = f"{ps.member_a.asn},{ps.member_b.asn}"
        key_ba = f"{ps.member_b.asn},{ps.member_a.asn}"
        peering_map[key_ab] = ps.status
        peering_map[key_ba] = ps.status

    context = {
        'participants': participants,
        'peering_map': peering_map,
    }
    return render(request, 'pages/peer_matrix.html', context)