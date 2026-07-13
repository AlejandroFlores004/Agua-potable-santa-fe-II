from django.shortcuts import render

# Create your views here.
def customer_home(request):
    return render(request, 'customer_home.html')