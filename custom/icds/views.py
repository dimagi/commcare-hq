from django.shortcuts import render


def tableau(request):
    return render(request, 'tableau.html')
