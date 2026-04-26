from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render

from .forms import PublicRegistrationForm
from .models import ParticipantRegistration, User


@login_required
def dashboard(request):
    return render(request, 'pages/dashboard.html')


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
    return render(request, 'pages/peer_matrix.html')
