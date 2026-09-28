#  i have created this file - GTA

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import Count
import re
from django.http import HttpRequest, HttpResponse

from datetime import timedelta
from django.utils import timezone

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Restaurant, Product, Transaction, RestGallery, RestFeedback, RestSale, CustomerCreditsData, CustomerData, Chatbot, CartDetails

import uuid, random, json, folium, ast, base64, geocoder

# from datetime import datetime, timedelta
from django.conf import settings

from django.contrib import messages
from textblob import TextBlob

GENAI_API_KEY_VALUE = settings.GEMINI_API_KEY

import google.generativeai as genai

genai.configure(api_key=GENAI_API_KEY_VALUE)

MAX_CONTEXT_LENGTH = 500

# Create your views here.

# $$$Client Side$$$


@login_required(login_url='user_login')
def welcome(request):
    categories = [{
        'emoji': '🍟',
        'name': 'Snacks'
    }, {
        'emoji': '🍢',
        'name': 'Starters'
    }, {
        'emoji': '🍽️',
        'name': 'Thali'
    }, {
        'emoji': '🍗',
        'name': 'Chicken'
    }, {
        'emoji': '🍕',
        'name': 'Pizza'
    }, {
        'emoji': '🍔',
        'name': 'Burger'
    }, {
        'emoji': '☕',
        'name': 'Coffee'
    }, {
        'emoji': '🥤',
        'name': 'Boba'
    }, {
        'emoji': '🍰',
        'name': 'Desserts'
    }, {
        'emoji': '🍝',
        'name': 'Pasta'
    }, {
        'emoji': '🥂',
        'name': 'Drinks'
    }, {
        'emoji': '🍦',
        'name': 'IceCream'
    }, {
        'emoji': '🦞',
        'name': 'Seafood'
    }, {
        'emoji': '🍛',
        'name': 'Biryani'
    }, {
        'emoji': '🥗',
        'name': 'Vegetarian'
    }, {
        'emoji': '🍬',
        'name': 'Sweets'
    }, {
        'emoji': '🥡',
        'name': 'Chinese'
    }, {
        'emoji': '🍛',
        'name': 'SouthIndian'
    }, {
        'emoji': '🍲',
        'name': 'NorthIndian'
    }, {
        'emoji': '🔥',
        'name': 'Tandoori'
    }, {
        'emoji': '🌮',
        'name': 'StreetFood'
    }]

    # Featured Restaurants (Top 5 by Rating)
    featured_restaurants = Restaurant.objects.order_by('-rating')[:5]

    # Most Dishes (Top 5 Restaurants with the Most Products)
    most_dishes_restaurants = (Restaurant.objects.annotate(
        product_count=Count('product')).order_by('-product_count')[:5])

    # Newly Arrived Dishes (Latest 5 Added Products)
    new_dishes = Product.objects.order_by('-createdon')[:6]

    # Nearest Restaurants (Filtered for Mumbai Dadar) - Mock Coordinates
    mumbai_lat, mumbai_lon = 19.0183, 72.8446
    nearest_restaurants = Restaurant.objects.filter(
        latitude="*",
        longitude="*")[:6]  # Dummy filter (replace with actual logic)

    # Get the most ordered restaurants (sorted by highest count of 'done' status)
    top_ordered_restaurants = (
        CartDetails.objects.filter(
            status="done")  # Filter only completed orders
        .values('restaurantname')  # Group by restaurant name
        .annotate(order_count=Count(
            'restaurantname'))  # Count occurrences of each restaurant
        .order_by('-order_count')
        [:5]  # Sort by highest order count and limit to top 5
    )

    # Fetch restaurant details from the Restaurant model based on names
    top_credit_restaurants = Restaurant.objects.filter(
        name__in=[r['restaurantname'] for r in top_ordered_restaurants])

    active_sale = RestSale.objects.filter(
        status="active").order_by('?').first()

    return render(
        request, 'client/welcome.html', {
            'featured_restaurants': featured_restaurants,
            'most_dishes_restaurants': most_dishes_restaurants,
            'new_dishes': new_dishes,
            'nearest_restaurants': nearest_restaurants,
            'top_credit_restaurants': top_credit_restaurants,
            'categories': categories,
            'activesale': active_sale
        })


def meOnMap(request):
    try:
        # Get user's IP address
        userIp = request.META.get('HTTP_X_FORWARDED_FOR')
        if userIp:
            userIp = userIp.split(',')[0]
        else:
            userIp = request.META.get('REMOTE_ADDR')

        # Fallback IP for localhost testing
        if userIp == '127.0.0.1':
            userIp = '8.8.8.8'  # Public IP example

        # Get location from IP
        location = geocoder.ip(userIp)
        if location.ok:
            userLatitude = location.latlng[0]
            userLongitude = location.latlng[1]
        else:
            userLatitude = 0
            userLongitude = 0

        # Create base map centered at user's location
        userMap = folium.Map(location=[userLatitude, userLongitude],
                             zoom_start=12)

        # Add user marker
        folium.Marker([userLatitude, userLongitude],
                      tooltip="You are here!",
                      icon=folium.Icon(color='blue')).add_to(userMap)

        # Fetch all restaurants
        allRestaurants = Restaurant.objects.all()

        # Add restaurant markers
        for restaurant in allRestaurants:
            try:
                if restaurant.latitude != "*" and restaurant.longitude != "*":
                    folium.Marker(
                        [
                            float(restaurant.latitude),
                            float(restaurant.longitude)
                        ],
                        tooltip=restaurant.name,
                        icon=folium.Icon(color='red',
                                         icon='cutlery',
                                         prefix='fa')).add_to(userMap)
            except Exception as innerError:
                print(
                    f"Error adding marker for restaurant {restaurant.name}: {innerError}"
                )

        # Generate map HTML
        mapHtml = userMap._repr_html_()

        return render(request, 'client/me_on_map.html', {'mapHtml': mapHtml})

    except Exception as e:
        print(f"Error in meOnMap view: {e}")
        return HttpResponse("Something went wrong. Please try again later.")


@login_required(login_url='user_login')
def categoryProducts(request, categoryName):
    """
    IO: Receives categoryName from URL.
    Working: Fetch products matching the category from database.
    Returns: Render 'category_products.html' with product list.
    """

    try:
        products = Product.objects.filter(
            category__iexact=categoryName).order_by('-createdon')
    except Product.DoesNotExist:
        products = []

    context = {'products': products, 'categoryName': categoryName}
    return render(request, 'client/category_products.html', context)


@login_required(login_url='user_login')
def menu(request):
    return render(request, 'client/menu.html')


# views.py


def notifications(request):
    # Get today's date
    today = timezone.now()

    # Filter newly added restaurants and products created within the last 3 days
    new_restaurants = Restaurant.objects.filter(created_on__gte=today -
                                                timedelta(days=3))
    old_restaurants = Restaurant.objects.filter(created_on__lt=today -
                                                timedelta(days=3))

    new_products = Product.objects.filter(createdon__gte=today -
                                          timedelta(days=3))
    old_products = Product.objects.filter(createdon__lt=today -
                                          timedelta(days=3))

    return render(
        request, 'client/notifications.html', {
            'new_restaurants': new_restaurants,
            'old_restaurants': old_restaurants,
            'new_products': new_products,
            'old_products': old_products
        })


def search(request):
    query = request.GET.get('q', '')  # Get search query from URL
    search_type = request.GET.get(
        'type',
        'product')  # Determine whether to search by product or restaurant

    # Get the latest 5 restaurants and products, randomly shuffle them
    latest_restaurants = Restaurant.objects.order_by(
        '-created_on')[:5]  # Get the most recent 5 restaurants
    latest_products = Product.objects.order_by(
        '-createdon')[:5]  # Get the most recent 5 products
    random_restaurants = random.sample(
        list(latest_restaurants),
        len(latest_restaurants))  # Shuffle the list randomly
    random_products = random.sample(
        list(latest_products),
        len(latest_products))  # Shuffle the list randomly

    if query:
        if search_type == 'product':
            # Search for products by name
            products = Product.objects.filter(name__icontains=query)
            return render(
                request, 'client/search_results.html', {
                    'products': products,
                    'query': query,
                    'search_type': search_type,
                    'random_restaurants': random_restaurants,
                    'random_products': random_products
                })
        elif search_type == 'restaurant':
            # Search for restaurants by name
            restaurants = Restaurant.objects.filter(name__icontains=query)
            return render(
                request, 'client/search_results.html', {
                    'restaurants': restaurants,
                    'query': query,
                    'search_type': search_type,
                    'random_restaurants': random_restaurants,
                    'random_products': random_products
                })
    else:
        return render(
            request, 'client/search.html', {
                'query': query,
                'random_restaurants': random_restaurants,
                'random_products': random_products
            })


@login_required(login_url='user_login')
def products(request):
    products = [
        {
            'name': "Cheese Burger",
            'description': "Tasty grilled burger",
            'price': 5.99,
            'image_url': 'https://via.placeholder.com/150'
        },
        {
            'name': "Pepperoni Pizza",
            'description': "Classic Italian pizza",
            'price': 8.99,
            'image_url': 'https://via.placeholder.com/150'
        },
    ]

    return render(request, 'client/products.html', {'products': products})


@login_required(login_url='user_login')
def profile(request):
    """
    Renders the user profile page.
    """
    # customer = CustomerData.objects.get(username=request.user)
    customer = get_object_or_404(CustomerData, username=request.user)
    if not customer:
        # return redirect('user_login')
        return redirect('welcome')

    creditdetails = CustomerCreditsData.objects.filter(
        username=request.user).first()
    transactioncount = Transaction.objects.filter(
        customername=request.user).count()

    return render(
        request, 'client/profile.html', {
            'customer': customer,
            'creditdetails': creditdetails,
            'transactioncount': transactioncount
        })


# @login_required(login_url='user_login')
# def cart(request):
#     return render(request, 'client/cart.html')


def qrscanner(request):
    return render(request, 'client/qrscanner.html')


def classifyEmotion(text):
    """
    classifyEmotion(text: str) -> str
    Classifies feedback into Positive, Negative, or Neutral using TextBlob.
    """
    try:
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity
        if polarity > 0:
            return "Positive"
        elif polarity < 0:
            return "Negative"
        else:
            return "Neutral"
    except Exception as e:
        print(f"Error classifying emotion: {e}")
        return "Neutral"


def submitFeedback(request):
    """
    submitFeedback(request) -> HttpResponse
    Handles POST request for feedback submission without using forms.py.
    """
    if request.method == 'POST':
        try:
            restaurantId = request.POST.get('restaurantId', '').strip()
            restaurantName = request.POST.get('restaurantName', '').strip()
            feedback = request.POST.get('feedback', '').strip()
            print("restaurantId : ", restaurantId)
            print("restaurantName : ", restaurantName)
            print("feedback : ", feedback)

            if not restaurantId or not restaurantName or not feedback:
                messages.error(request, "All fields are required.")
                return redirect(request.META.get('HTTP_REFERER', '/'))

            emotion = classifyEmotion(feedback)
            print("emotion : ", emotion)

            RestFeedback.objects.create(restaurantid=restaurantId,
                                        restaurantname=restaurantName,
                                        feedback=feedback,
                                        emotion=emotion)

            messages.success(request, "Feedback submitted successfully!")
            return redirect(request.META.get('HTTP_REFERER', '/'))

        except Exception as e:
            messages.error(request, f"Error submitting feedback: {str(e)}")
            return redirect(request.META.get('HTTP_REFERER', '/'))

    return redirect('welcome')


@login_required(login_url='user_login')
def addtocart(request, product_id):
    product = Product.objects.get(prodid=product_id)
    cart_item, created = CartDetails.objects.get_or_create(
        restaurantname=product.restaurant.name,
        username=request.user,
        productname=product.name,
        productprice=product.price,
        productimage=product.image,  # Store product image
        quantity=1,  # Default to quantity of 1
        extradetails=f"Product from {product.restaurant.name}",
        status="new")
    if not created:
        cart_item.status = "new"  # In case it was already in the cart, we reset status
        cart_item.save()
    return redirect('viewcart')  # After adding, redirect to cart view page


@login_required(login_url='user_login')
def viewcart(request):
    cart_items = CartDetails.objects.filter(
        username=request.user,
        status="new")  # Fetch all cart items for the user
    total_amount = sum([item.total_price() for item in cart_items
                        ])  # Calculate total using total_price() method
    return render(request, 'client/viewcart.html', {
        'cartData': cart_items,
        'totalAmount': total_amount
    })


@login_required(login_url='user_login')
def update_cart(request):
    """
    Handles cart updates (increase, decrease, remove)
    IO: cartId (GET param), action (GET param)
    Working: Update quantity or delete cart item, recalculate totals
    """
    try:
        cartId = request.GET.get('cartId')
        action = request.GET.get('action')

        cartItem = CartDetails.objects.get(cartid=cartId)

        if action == 'increase':
            cartItem.quantity += 1
            cartItem.save()

        elif action == 'decrease':
            if cartItem.quantity > 1:
                cartItem.quantity -= 1
                cartItem.save()
            else:
                cartItem.delete()  # Auto delete if quantity becomes 0

        elif action == 'remove':
            cartItem.delete()

        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid action'
            },
                                status=400)

        cartItems = CartDetails.objects.filter(username=request.user,
                                               status="new")
        totalAmount = sum([item.total_price() for item in cartItems])

        return JsonResponse({
            'success':
            True,
            'newQuantity':
            cartItem.quantity if action != 'remove' else 0,
            'newTotal':
            cartItem.total_price() if action != 'remove' else 0,
            'totalAmount':
            totalAmount
        })

    except CartDetails.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Cart item not found'
        },
                            status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# @login_required(login_url='user_login')
# def stripepayment(request):
#     # Get cart data for the logged-in user
#     cart_items = CartDetails.objects.all()  # You may want to filter by user if needed
#     total_amount = sum([item.total_price() for item in cart_items])  # Calculate total

#     return render(request, 'client/stripepayment.html', {
#         'cartData': cart_items,
#         'totalAmount': total_amount,
#     })


@login_required(login_url='user_login')
def stripepayment(request):
    """Handles the GET request to display the payment page with cart and credit details."""

    # Fetch cart items for the logged-in user
    cart_items = CartDetails.objects.filter(username=request.user,
                                            status="new")
    total_amount = sum([item.total_price()
                        for item in cart_items])  # Calculate total amount

    # Get or create the user's credit record
    # credit_data = CustomerCreditsData.objects.get_or_create(username=request.user)

    credit_data = CustomerCreditsData.objects.filter(
        username=request.user).first()

    if credit_data == None:
        credit_score = 0.0
    else:
        # Ensure creditscore is a float and handle missing values safely
        credit_score = float(
            credit_data.creditscore
        ) if credit_data and credit_data.creditscore is not None else 0.0

    return render(
        request, 'client/stripepayment.html', {
            'cartData':
            cart_items,
            'totalAmount':
            total_amount,
            'creditScore':
            credit_score,
            'creditMessage':
            "You don't have any credits to use."
            if credit_score == 0 else f"You have Rs. {credit_score} available."
        })


@login_required(login_url='user_login')
def process_payment(request):
    """Handles payment processing, cart updates, and credit score adjustments."""

    if request.method == 'POST':
        user = request.user
        cart_items = CartDetails.objects.filter(
            username=user, status="new")  # Fetch new cart items

        if not cart_items.exists():
            return redirect('stripepayment')  # No items, redirect to payment

        # Calculate total bill amount
        total_amount = sum(item.total_price() for item in cart_items)

        # Fetch or create user credit record
        credit_data, _ = CustomerCreditsData.objects.get_or_create(
            username=user)
        credit_score = float(credit_data.creditscore or 0.0)

        # Check if the user wants to use credits
        use_credits = request.POST.get('use_credits', 'off') == 'on'
        credit_used = min(credit_score, total_amount) if use_credits else 0
        final_bill = total_amount - credit_used  # Final amount after using credits

        # Calculate new credit score (10% of final bill)
        new_credits = final_bill * 0.1
        updated_credits = max(0, credit_score - credit_used) + new_credits

        # Save updated credit score
        credit_data.creditscore = updated_credits
        credit_data.save()

        # Store transaction record
        Transaction.objects.create(
            restaurantname=cart_items.first().
            restaurantname,  # Assuming all items from same restaurant
            customername=user.username,
            custmoreid=user.id,
            gotcreditscore=new_credits,
            dishdetails=str(list(
                cart_items.values())),  # Save cart details as JSON string
            billamount=total_amount,  # Original total bill
            discountamount=credit_used,
        )

        # Mark cart items as "done"
        cart_items.update(status="done")

        return redirect('successpaymentpage')  # Redirect to success page

    return redirect('homepage')  # If accessed via GET, redirect to home


# @login_required(login_url='user_login')
# def successpaymentpage(request):
#     # Logic for payment processing can be added here
#     return render(request, 'client/successpaymentpage.html')


@login_required(login_url='user_login')
def successpaymentpage(request):
    latest_transaction = Transaction.objects.filter(
        customername=request.user.username).latest('createdon')
    return render(request, "client/successpaymentpage.html",
                  {"transactionid": latest_transaction.transaction_id})


@login_required(login_url='user_login')
def transaction(request):
    # get the transaction for request.user
    # transactions = Transaction.objects.all().values(
    #     'transaction_id', 'restaurantname', 'customername', 'billamount',
    #     'discountamount', 'createdon')

    transactions = Transaction.objects.filter(customername=request.user).values(
        'transaction_id', 'restaurantname', 'customername',
        'billamount', 'discountamount', 'createdon'
    )
    
    return render(request, 'client/transaction.html',
                  {'transactions': list(transactions)})


@login_required(login_url='user_login')
def meonmap(request):
    return render(request, 'client/meonmap.html')


def limit_text(text, max_length=MAX_CONTEXT_LENGTH):
    """Trims text to fit within a max word limit."""
    words = text.split()
    return " ".join(words[:max_length]) if len(words) > max_length else text


# @login_required(login_url='user_login')
# def chatbot(request):
#     return render(request, 'client/chatbot.html')


def gptAI(prompt):
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    replyText = response.text
    # print(replyText)
    return replyText


@login_required(login_url='user_login')
def chatbot(request):
    if request.method == "POST":
        username = request.POST.get('username', 'Guest')
        query = request.POST.get('query')

        # 🟢 **Stage 1: Identify Relevant Data Based on Query Type**
        relevant_data = ""
        query_lower = query.lower()

        if any(keyword in query_lower for keyword in
               ["best restaurant", "top places", "recommend restaurant"]):
            restaurants = Restaurant.objects.order_by('-rating')[:5]
            relevant_data = json.dumps(
                list(restaurants.values('name', 'rating', 'address',
                                        'contact')))

        elif any(keyword in query_lower for keyword in
                 ["best dish", "recommended food", "top selling items"]):
            products = Product.objects.order_by(
                '-price')[:5]  # Sort by price or popularity
            relevant_data = json.dumps(
                list(products.values('name', 'category', 'price')))

        # elif any(keyword in query_lower
        #          for keyword in ["my transactions", "past orders", "bill"]):
        #     transactions = Transaction.objects.filter(
        #         customername=username)
        #     relevant_data = json.dumps(
        #         list(
        #             transactions.values('restaurantname', 'dishdetails',
        #                                 'billamount', 'createdon')))


        elif any(keyword in query_lower
            
            for keyword in ["my transactions", "past orders", "bill"]):
                transactions = Transaction.objects.filter(customername=username)
        
                # Convert 'createdon' to a string in ISO format
                relevant_data = json.dumps(
                    [
                        {
                            'restaurantname': transaction['restaurantname'],
                            'dishdetails': transaction['dishdetails'],
                            'billamount': transaction['billamount'],
                            'createdon': transaction['createdon'].isoformat()  # Convert datetime to string
                        }
                        for transaction in transactions.values('restaurantname', 'dishdetails', 'billamount', 'createdon')
                    ]
                )
                relevant_data = str(relevant_data)
        
        
        elif any(keyword in query_lower
                 for keyword in ["my credits", "loyalty points"]):
            credits = CustomerCreditsData.objects.filter(
                username=request.user).order_by('-creditscore')
            relevant_data = json.dumps(
                list(credits.values('username', 'creditscore')))

        else:
            # relevant_data = "General chatbot conversation."


            # Query all Product records
            products = Product.objects.all()
    
            # Initialize an empty list to store formatted strings
            product_details = []
    
            for product in products:
                # Create a string for each product with restaurant name, category, and price
                product_info = f"Restaurant: {product.restaurant.name}, Category: {product.category}, Price: Rs.{product.price}"
                product_details.append(product_info)
    
            # Join all the product strings into a single string
            relevant_data = "\n".join(product_details)



        

        relevant_data = limit_text(relevant_data)  # Limit text length
        print(f"relevant_data : {relevant_data}")
        # Fetch last 10 chat messages (context)
        messages = Chatbot.objects.filter(
            username=username).order_by('-timestamp')[:10]
        messages_json = json.dumps(list(messages.values('query', 'response')))

        # 🟢 **Stage 2: Generate AI Response Using GPT**
        prompt = f"""
        Act as a Smart AI Food Assistant. Analyze past user queries and recommend the best choices based on history, restaurant ratings, product popularity, and user credits.

        - User: {username}
        - Query: {query}
        - Relevant Data: {relevant_data}
        - Chat History: {messages_json}

        Note : 
        - Strictly Give response in HTML where style it using tailwind css only and normal.
        - Do not add any other text except the response.
        - If any links then use a tag with target attribute set to _blank.
        - if any img you want to show then use img tag.
        - Always close the html tag.

        Provide the most **useful and precise** recommendations based on available data.
        Very sometimes ask question if needed else give the reply with actual data what user wants.
        Use max text size = text-xl and max padding as p-2
        """
        prompt = re.sub(r'\s+', ' ', prompt).strip()  # Clean whitespace

        print(f"Prompt Sent to GPT: {prompt[:200]}...")  # Debugging (print first 200 chars)

        response = str(gptAI(prompt))  # Call AI
        response = response.replace("```html", "")
        response = response.replace("```", "")
        # response = response[:500]  # Limit response length

        # Save chat in DB
        Chatbot.objects.create(username=username,
                               query=query,
                               response=response)

        # return render(request, 'client/chatbot.html', {
        #     'messages': messages,
        #     'username': username
        # })
        return redirect('chatbot')

    # GET request: Show chat history
    username = request.user.username if request.user.is_authenticated else "Guest"
    messages = Chatbot.objects.filter(username=username).order_by('timestamp')
    # messages = Chatbot.objects.filter(username=username)[:10]
    return render(request, 'client/chatbot.html', {
        'messages': messages,
        'username': username
    })


# Account : Register, Login, Logout


def user_register(request):
    error_message = None

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        email = request.POST['email']
        phonenumber = request.POST['phonenumber']
        profile_image = request.FILES.get(
            'profile_image')  # Get uploaded image

        # Check if the username is unique
        if not User.objects.filter(username=username).exists():
            # Convert the image to Base64
            baseimg = "*"
            if profile_image:
                baseimg = "data:image/jpeg;base64," + base64.b64encode(
                    profile_image.read()).decode('utf-8')

            # Create a new user
            user = User.objects.create_user(username=username,
                                            password=password,
                                            email=email)

            # Create a CustomerData entry with the Base64 image
            CustomerData.objects.create(
                username=user,
                contact=phonenumber,
                email=email,
                baseimg=baseimg  # Store Base64-encoded image
            )

            return redirect('user_login')  # Redirect to login page
        else:
            error_message = 'Username already exists'

    return render(request, 'client/register.html',
                  {'error_message': error_message})


def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('welcome')
        else:
            error_message = 'Invalid username or password'
    else:
        error_message = None

    return render(request, 'client/login.html',
                  {'error_message': error_message})


def user_logout(request):
    logout(request)
    return redirect('user_login')


def productdetails(request, prodid):
    # Get the product by its ID
    product = get_object_or_404(Product, prodid=prodid)

    # Render the product details template with the product data
    return render(request, 'restaurant/product_details.html',
                  {'product': product})


def restpublicprofile(request, restaurant_id):
    """
    View to display the restaurant profile page, including restaurant details,
    gallery, products, sales, and feedback.
    """
    try:
        # Fetch the restaurant by its ID
        restaurant = Restaurant.objects.get(restaurantid=restaurant_id)

        # Fetch the related data for this restaurant
        gallery = RestGallery.objects.filter(restaurantid=restaurant_id)
        products = Product.objects.filter(restaurant=restaurant)
        sales = RestSale.objects.filter(restaurantid=restaurant_id,
                                        status="active")
        feedbacks = RestFeedback.objects.filter(restaurantid=restaurant_id)

        # Render the template with all the data
        context = {
            'restaurant': restaurant,
            'gallery': gallery,
            'products': products,
            'sales': sales,
            'feedbacks': feedbacks,
        }

        return render(request, 'restaurant/restpublicprofile.html', context)

    except Restaurant.DoesNotExist:
        # If the restaurant doesn't exist, redirect or show an error message
        return render(request, 'restaurant/error.html',
                      {'message': 'Restaurant not found'})


# $$$Restaurant Side$$$

# -------------------------
# Authentication Views
# -------------------------


def restaurantregister(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        email = request.POST['email']
        name = request.POST['restaurant_name']
        contact = request.POST['contact']
        address = request.POST['address']
        website = request.POST['website']
        latitude = request.POST['latitude']
        longitude = request.POST['longitude']
        logo = request.FILES.get('logo')  # Get the uploaded logo

        # Check if the logo exists, then convert it to base64
        logo_base64 = "*"
        if logo:
            try:
                logo_data = logo.read()
                logo_base64 = base64.b64encode(logo_data).decode('utf-8')
            except Exception:
                logo_base64 = "*"

        # Check if the username already exists
        if User.objects.filter(username=username).exists():
            return render(request, 'restaurant/register.html',
                          {'error_message': 'Username already exists!'})

        if not website:
            website = "*"
        if not latitude:
            latitude = "*"
        if not longitude:
            longitude = "*"

        # Create user and restaurant atomically
        user = User.objects.create_user(username=username,
                                        password=password,
                                        email=email)

        restaurant = Restaurant.objects.create(
            owner=user,
            name=name,
            contact=contact,
            address=address,
            email=email,
            website=website,
            latitude=latitude,
            longitude=longitude,
            baseimg=logo_base64 or "*"
        )

        # Log the user in and redirect to the dashboard
        login(request, user)
        return redirect('restaurantdashboard')

    return render(request, 'restaurant/register.html')


def restaurantlogin(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            return redirect('restaurantdashboard')
        else:
            return render(request, 'restaurant/login.html',
                          {'error': 'Invalid credentials!'})

    return render(request, 'restaurant/login.html')


def restaurantlogout(request):
    logout(request)
    return redirect('restaurantlogin')


# -------------------------
# Dashboard & Profile
# -------------------------


@login_required
def restaurantdashboard(request):
    restaurant = get_object_or_404(Restaurant, owner=request.user)
    total_products = Product.objects.filter(restaurant=restaurant).count()
    total_offers = RestSale.objects.filter(
        restaurantname=restaurant.name).count()

    total_transactions = Transaction.objects.filter(
        restaurantname=restaurant.name).count()
    revenue = sum(transaction.billamount
                  for transaction in Transaction.objects.filter(
                      restaurantname=restaurant.name))

    context = {
        'restaurant': restaurant,
        'total_products': total_products,
        'total_transactions': total_transactions,
        'total_offers': total_offers,
        'revenue': revenue,
    }
    return render(request, 'restaurant/dashboard.html', context)


@login_required
def restaurantprofile(request):
    restaurant = get_object_or_404(Restaurant, owner=request.user)

    if request.method == 'POST':
        restaurant.name = request.POST['name']
        restaurant.contact = request.POST['contact']
        restaurant.address = request.POST['address']
        restaurant.website = request.POST.get('website', '')

        restaurant.save()
        return redirect('restaurantprofile')

    return render(request, 'restaurant/profile.html',
                  {'restaurant': restaurant})


@login_required
def restaurantGallery(request):
    restaurant = get_object_or_404(Restaurant, owner=request.user)
    gallery = RestGallery.objects.filter(
        restaurantid=restaurant.restaurantid
    )  # Use restaurant.id instead of restaurantid

    if request.method == 'POST':
        try:
            title = request.POST['title']
            image = request.FILES.get('image')

            if not image:
                raise ValueError("Image file is required")

            # Convert image to base64
            if isinstance(image, InMemoryUploadedFile):
                image_data = image.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')
            else:
                raise ValueError("Invalid image file")

            # Save image in gallery
            RestGallery.objects.create(
                restaurantid=restaurant.
                restaurantid,  # Using restaurant.id here as well
                restaurantname=restaurant.name,
                title=title,
                baseimg="data:image/jpeg;base64," + image_base64)

            return redirect('restaurantGallery')

        except Exception as e:
            print(f"Error uploading image: {e}")
            return render(request, 'restaurant/gallery.html', {
                'gallery': gallery,
                'error': str(e)
            })

    return render(request, 'restaurant/gallery.html', {'gallery': gallery})


@login_required
def restaurantGalleryDelete(request, gallery_id):
    """
    Deletes an image from the gallery.
    """
    try:
        # Ensure the image belongs to the logged-in restaurant
        restaurant = request.user.restaurant  # Get the restaurant associated with the logged-in user
        image = get_object_or_404(RestGallery,
                                  galleryid=gallery_id,
                                  restaurantid=restaurant.restaurantid)

        # Delete the image from the gallery
        image.delete()
        return redirect(
            'restaurantGallery')  # Redirect to the gallery page after deletion

    except Exception as e:
        print(f"Error deleting image: {e}")
        return redirect('restaurantGallery')  # Redirect in case of error


@login_required
def restaurantfeedback(request):
    """
    Displays a list of feedbacks for the restaurant.
    """
    # Get the restaurant owned by the logged-in user
    restaurant = get_object_or_404(Restaurant, owner=request.user)

    # Fetch all feedbacks related to the restaurant
    feedbacks = RestFeedback.objects.filter(
        restaurantid=restaurant.restaurantid)

    # Render the feedbacks in the template
    return render(request, 'restaurant/feedback.html', {
        'feedbacks': feedbacks,
        'restaurant': restaurant
    })


@login_required
def restaurantsales(request):
    """
    View to display all sales with filtering options (incoming, active, closed).
    """
    restaurant = get_object_or_404(Restaurant, owner=request.user)

    # Get the filter status from GET parameters (if any)
    sale_status = request.GET.get('status', 'all')  # Default is 'all'

    # Filter sales based on the status
    if sale_status == 'all':
        sales = RestSale.objects.filter(restaurantid=restaurant.restaurantid)
    else:
        sales = RestSale.objects.filter(restaurantid=restaurant.restaurantid,
                                        status=sale_status)

    # Count the sales for each status
    incoming_count = RestSale.objects.filter(
        restaurantid=restaurant.restaurantid, status='incoming').count()
    active_count = RestSale.objects.filter(
        restaurantid=restaurant.restaurantid, status='active').count()
    closed_count = RestSale.objects.filter(
        restaurantid=restaurant.restaurantid, status='closed').count()

    return render(
        request, 'restaurant/view_sales.html', {
            'sales':
            sales,
            'status':
            sale_status,
            'all_count':
            int(incoming_count) + int(active_count) + int(closed_count),
            'incoming_count':
            incoming_count,
            'active_count':
            active_count,
            'closed_count':
            closed_count
        })


import base64
from django.core.files.uploadedfile import InMemoryUploadedFile
from io import BytesIO
from PIL import Image


@login_required
def restaurantsalesadd(request):
    """
    Add a new sale and convert image to base64 before saving it in the database.
    """
    if request.method == 'POST':
        # Get form data from the POST request
        title = request.POST['title']
        description = request.POST['description']
        startdate = request.POST['startdate']
        enddate = request.POST['enddate']
        status = request.POST['status']
        image = request.FILES.get('baseimg')  # Get the image file

        # If an image is provided, convert it to base64
        baseimg = None
        if image:
            # Convert the image to base64
            image_data = image.read()  # Read image data
            baseimg = "data:image/jpeg;base64," + base64.b64encode(
                image_data).decode(
                    'utf-8')  # Convert to base64 and decode to string

        # Get the restaurant object
        restaurant = get_object_or_404(Restaurant, owner=request.user)

        # Create and save the new sale
        RestSale.objects.create(
            restaurantid=restaurant.restaurantid,
            restaurantname=restaurant.name,
            title=title,
            description=description,
            startdate=startdate,
            enddate=enddate,
            status=status,
            baseimg=baseimg  # Save the base64 image string
        )

        return redirect('restaurantsales')  # Redirect after saving

    return render(request, 'restaurant/add_sale.html')


@login_required
def restaurantsalesedit(request, sale_id):
    """
    Edit an existing sale and convert image to base64 before saving it in the database.
    """
    sale = get_object_or_404(RestSale,
                             saleid=sale_id,
                             restaurantid=request.user.restaurant.restaurantid)

    if request.method == 'POST':
        # Get form data from the POST request
        title = request.POST['title']
        description = request.POST['description']
        startdate = request.POST['startdate']
        enddate = request.POST['enddate']
        status = request.POST['status']
        image = request.FILES.get('baseimg')  # Get the image file

        # If an image is provided, convert it to base64
        baseimg = sale.baseimg  # Keep the old image if not updated
        if image:
            # Convert the image to base64
            image_data = image.read()  # Read image data
            baseimg = "data:image/jpeg;base64," + base64.b64encode(
                image_data).decode(
                    'utf-8')  # Convert to base64 and decode to string

        # Update the sale with new data
        sale.title = title
        sale.description = description
        sale.startdate = startdate
        sale.enddate = enddate
        sale.status = status
        sale.baseimg = baseimg  # Save the base64 image string

        sale.save()  # Save the changes

        return redirect('restaurantsales')  # Redirect to the view sales page

    return render(request, 'restaurant/edit_sale.html', {'sale': sale})


# -------------------------
# Products Management
# -------------------------


@login_required
def restaurantallproducts(request):
    restaurant = get_object_or_404(Restaurant, owner=request.user)
    products = Product.objects.filter(restaurant=restaurant)
    return render(request, 'restaurant/productlist.html',
                  {'products': products})


@login_required
def restaurantaddproduct(request):
    if request.method == 'POST':
        try:
            name = request.POST['name']
            category = request.POST['category']
            price = float(request.POST['price'])
            image = request.FILES.get('image')

            if not image:
                raise ValueError("Image file is required")

            # Convert image to base64
            if isinstance(image, InMemoryUploadedFile):
                image_data = image.read()  # Read image file
                image_base64 = base64.b64encode(image_data).decode(
                    'utf-8')  # Convert to base64
            else:
                raise ValueError("Invalid image file")

            restaurant = get_object_or_404(Restaurant, owner=request.user)

            # Save product with base64 image
            Product.objects.create(restaurant=restaurant,
                                   name=name,
                                   category=category,
                                   price=price,
                                   image="data:image/jpeg;base64," +
                                   image_base64)

            return redirect('restaurantallproducts')

        except Exception as e:
            print(f"error : {e}")
            return render(request, 'restaurant/addproduct.html',
                          {'error': str(e)})

    return render(request, 'restaurant/addproduct.html')


@login_required
def restauranteditproduct(request, product_id):
    product = get_object_or_404(Product,
                                prodid=product_id)  # Fix: `prodid`, not `id`

    if request.method == 'POST':
        try:
            product.name = request.POST['name']
            product.category = request.POST['category']
            product.price = float(request.POST['price'])

            if 'image' in request.FILES:
                image = request.FILES['image']

                # Convert image to base64
                if isinstance(image, InMemoryUploadedFile):
                    image_data = image.read()
                    image_base64 = base64.b64encode(image_data).decode('utf-8')
                    product.image = "data:image/jpeg;base64," + image_base64
                else:
                    raise ValueError("Invalid image file")

            product.save()
            return redirect('restaurantallproducts')

        except Exception as e:
            print(f"error : {e}")
            return render(request, 'restaurant/restaurant_editproduct.html', {
                'product': product,
                'error': str(e)
            })

    return render(request, 'restaurant/editproduct.html', {'product': product})


@login_required
def restaurantDeleteProduct(request, product_id):
    """
    Deletes a product by its ID.
    - Ensures that only the restaurant owner can delete their own products.
    - Handles exceptions gracefully.
    """
    try:
        product = get_object_or_404(Product,
                                    prodid=product_id,
                                    restaurant__owner=request.user)
        product.delete()
        return redirect('restaurantallproducts')

    except Exception as e:
        print(f"Error deleting product: {e}")
        return redirect('restaurantallproducts')


# -------------------------
# Transactions
# -------------------------


@login_required
def restauranttransactions(request):
    """
    Display the list of transactions, a leaderboard of the top 3 customers, 
    and a full list of all customers with their transaction count.
    """
    restaurant = get_object_or_404(Restaurant, owner=request.user)

    # Get all transactions for the restaurant
    transactions = Transaction.objects.filter(restaurantname=restaurant.name)

    # Aggregate transaction count per customer
    customer_transactions = (
        transactions.values('customername',
                            'custmoreid')  # Group by customer name and ID
        .annotate(transaction_count=Count('tid'))  # Count transactions
        .order_by('-transaction_count')  # Sort in descending order
    )

    # Get the top 3 customers
    top_customers = customer_transactions[:3]  # Get the first 3 customers

    return render(
        request, 'restaurant/transaction.html', {
            'transactions': transactions,
            'top_customers': top_customers,
            'customer_transactions': customer_transactions
        })


# @login_required
# def viewNodes(request):
#     try:

#         user_nodes = Nodedata.objects.filter(user_name=request.user.username)
#         user_clusterdata = Clusterdata.objects.filter(
#             user_name=request.user.username)
#         # print("user_nodes : ", user_nodes)
#         # print("username : ", request.user.username)

#         # Pass the list of nodes to the template
#         context = {
#             'user_nodes': user_nodes,
#             'user_clusterdata': user_clusterdata,
#         }
#         return render(request, 'agroapp/nodes.html', context)

#     except:
#         return render(request, 'agroapp/nodes.html')

# @login_required
# def addnode(request):
#     if request.method == 'POST':
#         user_name = request.POST.get('user_name')
#         node_name = request.POST.get('node_name')
#         Loc_lat = request.POST.get('lat')
#         Loc_long = request.POST.get('long')
#         api_key = generate_unique_api_key()

#         # Create a new node
#         Nodedata.objects.create(user_name=user_name,
#                                 node_name=node_name,
#                                 Loc_lat=Loc_lat,
#                                 Loc_long=Loc_long,
#                                 api_key=api_key)

#         # Redirect to a success page or another view
#         return redirect(
#             'viewNodes'
#         )  # Change 'node_list' to the actual URL name for the node list view

#     return render(request, 'agroapp/addnode.html')

# @login_required
# def addcluster(request):
#     if request.method == 'POST':
#         selected_nodes = request.POST.getlist('selected_nodes')
#         user_name = request.user.username
#         cluster_name = request.POST.get('cluster_name')

#         print("Selected Nodes:", selected_nodes, user_name, cluster_name)

#         # Create a new node
#         Clusterdata.objects.create(user_name=user_name,
#                                    cluster_name=cluster_name,
#                                    clust_data=selected_nodes)

#         # Redirect to a success page or another view
#         return redirect(
#             'viewNodes'
#         )  # Change 'node_list' to the actual URL name for the node list view

#     user_nodes = Nodedata.objects.filter(user_name=request.user.username)
#     context = {
#         'user_nodes': user_nodes,
#     }
#     return render(request, 'agroapp/addcluster.html', context)

# def get_the_map(lat, long, node_name):
#     # Specify the latitude and longitude
#     # lat, lon = 123.13, 123.34

#     # Create a Folium map centered at the specified location
#     my_map = folium.Map(location=[lat, long], zoom_start=16)

#     # Add a marker at the specified location
#     folium.Marker([lat, long], popup=node_name).add_to(my_map)
#     # folium.Marker([lat, long], popup=node_name, icon=folium.Icon(color='red')).add_to(my_map)

#     # Convert the map to HTML
#     map_html = my_map._repr_html_()
#     return map_html

#     # Pass the HTML content to the template
#     # return render(request, 'mymaps.html', {'map_html': map_html})

# def get_the_map_multipal_loc(locations):
#     # Create a Folium map centered at the first location
#     first_location = locations[0]

#     my_map = folium.Map(
#         location=[first_location['lat'], first_location['long']],
#         zoom_start=16)

#     # Add markers for each location
#     for location in locations:
#         folium.Marker([location['lat'], location['long']],
#                       popup=location['node_name']).add_to(my_map)

#     # Convert the map to HTML
#     map_html = my_map._repr_html_()
#     return map_html

# @login_required
# def viewNodeData(request):
#     # Get parameters from the GET request

#     # username = request.GET.get('username', '')  # Hacker Trap
#     # username = request.user.username
#     nodename = request.GET.get('nodename', '')
#     # lat = request.GET.get('lat', '')
#     # long = request.GET.get('long', '')

#     if Nodedata.objects.filter(node_name=nodename).exists():
#         # Use the parameters as needed in your view logic
#         try:
#             # Example: Retrieve sensor data based on the node name

#             sensor_data = SensorData.objects.filter(
#                 nodename=nodename).order_by('-timestamp')
#             # sensor_data = SensorData.objects.filter(nodename=nodename)

#             # Retrieve the latest data for the specified nodename
#             latest_sensor_data = SensorData.objects.filter(
#                 nodename=nodename).order_by('-timestamp').first()

#             latest_5_sensor_data_list = SensorData.objects.filter(
#                 nodename=nodename).order_by('-timestamp')[:5]
#             latest_5_sensor_data_list = latest_5_sensor_data_list[::-1]

#             # if not latest_5_sensor_data_list:
#             # latest_5_sensor_data_list = latest_sensor_data
#             # latest_sensor_data = "null"

#         except:
#             sensor_data = "null"
#             latest_sensor_data = "null"
#             latest_5_sensor_data_list = "null"

#         user_node_data = Nodedata.objects.filter(node_name=nodename).first()

#         if user_node_data:
#             api_key = user_node_data.api_key
#             user_name = user_node_data.user_name
#             lat = user_node_data.Loc_lat
#             long = user_node_data.Loc_long
#         else:
#             api_key = 'Not available'
#             user_name = 'Not available'
#             lat = 'Not available'
#             long = 'Not available'

#         map_html = get_the_map(lat, long, nodename)

#         # Pass data to the template
#         context = {
#             'username': user_name,
#             'nodename': nodename,
#             'lat': lat,
#             'long': long,
#             'api_key': api_key,
#             'sensor_data': sensor_data,
#             'latest_data': latest_sensor_data,
#             'map_html': map_html,
#             'latest_5_sensor_data_list': latest_5_sensor_data_list,
#         }
#         return render(request, 'agroapp/nodedata.html', context)
#     else:
#         context = {"message": "wrong_route"}
#         return render(request, 'agroapp/nodedata.html', context)

# @login_required
# def viewclusterData(request):

#     # username = request.GET.get('username', '')  # Hacker Trap
#     # username = request.user.username
#     clustername = request.GET.get('clustername', '')

#     if Clusterdata.objects.filter(cluster_name=clustername).exists():
#         try:

#             cluster_data = Clusterdata.objects.filter(cluster_name=clustername)
#             # Extract 'clust_data' from each object and store it in a list
#             list_of_clust_data = [entry.clust_data for entry in cluster_data]

#             all_node_names = ast.literal_eval(list_of_clust_data[0])
#             all_nodeData = []

#             for item in all_node_names:
#                 __nodedata = Nodedata.objects.filter(node_name=item).first()
#                 all_nodeData.append(__nodedata)

#             locations = []
#             all_sensor_data = {nodeName: [] for nodeName in all_node_names}
#             all_latest_sensor_data = []
#             all_latest_5_sensor_data_list = []

#             for node_D in all_nodeData:
#                 locations.append({
#                     'lat': node_D.Loc_lat,
#                     'long': node_D.Loc_long,
#                     'node_name': node_D.node_name
#                 })

#             for __nodeNames in all_node_names:
#                 # print("__nodeNames : ",__nodeNames)

#                 valu = SensorData.objects.filter(
#                     nodename=__nodeNames).order_by('-timestamp')

#                 # print("valu : ", valu)

#                 all_sensor_data[__nodeNames].append(valu)
#                 # values['dadar'].append('Data 1 for Dadar')

#                 # print("all all_sensor_data :", all_sensor_data)

#                 all_latest_sensor_data.append(
#                     SensorData.objects.filter(
#                         nodename=__nodeNames).order_by('-timestamp').first())

#                 ___all_lat_5_sensor_data_list = SensorData.objects.filter(
#                     nodename=__nodeNames).order_by('-timestamp')[:5]
#                 ___all_lat_5_sensor_data_list = ___all_lat_5_sensor_data_list[::
#                                                                               -1]
#                 all_latest_5_sensor_data_list.append(
#                     ___all_lat_5_sensor_data_list)

#             # print("all_latest_5_sensor_data_list :", all_latest_5_sensor_data_list)

#             # user_node_data = Nodedata.objects.filter(node_name=nodename).first()
#             # sensor_data = SensorData.objects.filter(nodename=nodename)

#             # print("locations : ", locations)
#             map_html = get_the_map_multipal_loc(locations)

#         except:
#             all_sensor_data = "null"
#             all_latest_sensor_data = "null"
#             all_latest_5_sensor_data_list = "null"
#             map_html = "null"

#         # print("all_latest_5_sensor_data_list : " , all_latest_5_sensor_data_list)
#         # Pass data to the template
#         context = {
#             # 'username': user_name,
#             'clustername': clustername,
#             # 'lat': lat,
#             # 'long': long,
#             # 'api_key': api_key,
#             'all_sensor_data': all_sensor_data,
#             'all_latest_sensor_data': all_latest_sensor_data,
#             'all_latest_5_sensor_data_list': all_latest_5_sensor_data_list,
#             'map_html': map_html,
#         }
#         return render(request, 'agroapp/clusterdata.html', context)

#     else:
#         context = {"message": "wrong_route"}
#         return render(request, 'agroapp/clusterdata.html', context)

# def user_register(request):
#     if request.method == 'POST':
#         username = request.POST['username']
#         password = request.POST['password']
#         email = request.POST['email']

#         # Check if the username is unique
#         if not User.objects.filter(username=username).exists():
#             # Create a new user
#             user = User.objects.create_user(username=username,
#                                             password=password,
#                                             email=email)
#             return redirect('user_login')  # Redirect to your login view
#         else:
#             error_message = 'Username already exists'
#     else:
#         error_message = None

#     return render(request, 'agroapp/register.html',
#                   {'error_message': error_message})

# def user_login(request):
#     if request.method == 'POST':
#         username = request.POST['username']
#         password = request.POST['password']
#         user = authenticate(request, username=username, password=password)
#         if user is not None:
#             login(request, user)
#             return redirect('viewNodes')  # Redirect to your dashboard view
#         else:
#             error_message = 'Invalid username or password'
#     else:
#         error_message = None

#     return render(request, 'agroapp/login.html',
#                   {'error_message': error_message})

# def user_logout(request):
#     logout(request)
#     return redirect('user_login')  # Redirect to your login view

# route : http://127.0.0.1:8000/read_sensor_data/?username=sahil&api_key=5df155f4-9161-44b9-8ff5-9c821709e1bf&nodename=node_dadar

# def read_sensor_data(request):
#     if request.method == 'GET':
#         username = request.GET.get('username', '')
#         api_key = request.GET.get('api_key', '')
#         nodename = request.GET.get('nodename', '')

#         # Validate the username, API key, and nodename
#         user_node_data = Nodedata.objects.filter(user_name=username,
#                                                  api_key=api_key,
#                                                  node_name=nodename).first()

#         if user_node_data:
#             sensor_data = SensorData.objects.filter(nodename=nodename)
#             # Convert QuerySet to a list of dictionaries
#             sensor_data_list = list(sensor_data.values())

#             ret_data = {
#                 'user_name': username,
#                 'node_name': nodename,
#                 'sensor_Data': sensor_data_list,
#             }
#             return JsonResponse(ret_data)
#         else:
#             return JsonResponse({
#                 'status':
#                 'error',
#                 'message':
#                 'Invalid username, API key, or nodename'
#             })

#     return JsonResponse({
#         'status': 'error',
#         'message': 'Invalid request method'
#     })

# route : http://127.0.0.1:8000/sensordata/?username=sahil&api_key=5df155f4-9161-44b9-8ff5-9c821709e1bf&nodename=node_dadar&Depth_1=45.3&Depth_2=49.3&Depth_3=55.9&temperature=55.9&humidity=55.9

# def get_formatted_datetime():
#     # Get the current date and time
#     now = datetime.now()

#     # Add 6 hours to the current time
#     future_time = now + timedelta(hours=6)

#     # Define the month names
#     month_names = [
#         "January", "February", "March", "April", "May", "June", "July",
#         "August", "September", "October", "November", "December"
#     ]

#     # Extract the components of the date and time
#     month = month_names[future_time.month - 1]  # Adjust index to start from 0
#     day = future_time.day
#     year = future_time.year
#     hour = future_time.strftime("%I")  # 12-hour format
#     minute = future_time.minute
#     ampm = future_time.strftime("%p").lower()  # AM or PM

#     # Format the date and time string
#     formatted_date_time = f"{month} {day}, {year}, {hour}:{minute} {ampm}."

#     return formatted_date_time

# @csrf_exempt
# def sensor_data(request):
#     if request.method == 'GET':
#         # Get parameters from the GET request
#         username = request.GET.get('username', '')
#         api_key = request.GET.get('api_key', '')
#         nodename = request.GET.get('nodename', '')

#         depth_1 = float(request.GET.get('Depth_1', None))
#         depth_2 = float(request.GET.get('Depth_2', None))
#         depth_3 = float(request.GET.get('Depth_3', None))

#         temperature = float(request.GET.get('temperature', None))
#         humidity = float(request.GET.get('humidity', None))

#         timestampManual = get_formatted_datetime()
#         print("timestampManual :", timestampManual)

#         # Validate the username, API key, and nodename
#         user_node_data = Nodedata.objects.filter(user_name=username,
#                                                  api_key=api_key,
#                                                  node_name=nodename).first()

#         if user_node_data:
#             # Save data to the database
#             sensor_data = SensorData(
#                 nodename=nodename,
#                 depth_1=depth_1,
#                 depth_2=depth_2,
#                 depth_3=depth_3,
#                 temperature=temperature,
#                 humidity=humidity,
#                 timestamp=timestampManual  # Set the timestamp manually
#             )
#             sensor_data.save()

#             return JsonResponse({'status': 'success'})
#         else:
#             return JsonResponse({
#                 'status':
#                 'error',
#                 'message':
#                 'Invalid username, API key, or nodename'
#             })

#     return JsonResponse({
#         'status': 'error',
#         'message': 'Invalid request method'
#     })
'''
node_prabhadevi
9650ad02-52e0-4825-8f63-ef2b5235ee77

node_dadar
5df155f4-9161-44b9-8ff5-9c821709e1bf
'''
'''
import random

def generate_api_key():
    key_length = 36  # Length of the API key
    dash_positions = [8, 13, 18, 23]  # Positions of dashes in the API key

    characters = "abcdef0123456789"

    api_key = ''.join(random.choice(characters) if i not in dash_positions else '-' for i in range(key_length))
    return api_key

# Example usage
api_key = generate_api_key()
print(api_key)

'''

# def generate_api_key():
#     key_length = 36  # Length of the API key
#     dash_positions = [8, 13, 18, 23]  # Positions of dashes in the API key

#     characters = "abcdefghijklmnopqrstwxyz0123456789"

#     api_key = ''.join(
#         random.choice(characters) if i not in dash_positions else '-'
#         for i in range(key_length))
#     return api_key

# def generate_unique_api_key():
#     while True:
#         # api_key = str(uuid.uuid4())
#         api_key = str(generate_api_key())
#         if not Nodedata.objects.filter(api_key=api_key).exists():
#             return api_key

# def your_view_function(request):
#     # Your view logic here
#     api_key = generate_unique_api_key()

#     # Use api_key in your view logic or save it to the database

#     return HttpResponse(f"Generated API Key: {api_key}")

# ------------------------------------
# Sample Code Below
# ------------------------------------

# def index(request):
#     products = Product.objects.all()

#     all_prods = []
#     catProds = Product.objects.values('category', 'Product_id')
#     cats = {item['category'] for item in catProds}
#     for cat in cats:
#         prod = Product.objects.filter(category=cat)
#         n = len(products)
#         all_prods.append([prod, n])

#     params = {
#         'catproducts' : all_prods,
#         'allproducts' : products,
#               }

#     return render(request,'tze/index.html', params)

# def business(request):
#     # return HttpResponse('Teamzeffort    |      business Page')
#     return render(request,'tze/business.html')

# def about(request):
#     return render(request,'tze/about.html')

# def contact(request):
#     coreMem = Contact.objects.filter(mem_tag="core")
#     teamMem = Contact.objects.filter(mem_tag="team")
#     # print(f"coreMem: {coreMem} \n teamMem: {teamMem}")

#     return render(request, 'tze/contact.html', {'core':coreMem,'team':teamMem })

# def productView(request, myslug):
#     # Fetch the product using the id
#     product = Product.objects.filter(slug=myslug)
#     prodCat = product[0].category
#     # print(prodCat)
#     recproduct = Product.objects.filter(category=prodCat)
#     # print(recproduct)

#     # randomObjects = random.sample(recproduct, 2)
#     randomObjects = random.sample(list(recproduct), 2)

#     return render(request, 'tze/prodView.html', {'product':product[0],'recprod':randomObjects })

# # def index(request):
# #     return HttpResponse('Teamzeffort    |      index Page')
