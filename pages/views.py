from django.shortcuts import render

def dashboard(request):
    return render(request, 'pages/dashboard.html')

def register(request):
    return render(request, 'pages/register.html')

def documentation(request):
    return render(request, 'pages/documentation.html')

def peer_matrix(request):
    return render(request, 'pages/peer_matrix.html')