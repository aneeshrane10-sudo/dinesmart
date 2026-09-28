from django.db import models
from django.contrib.auth.models import User

import random
import string
from django.db import models
from django.utils import timezone


# Function to generate 10-digit unique ID
def generate_transaction_id() -> str:
    """Generates a 10-digit unique transaction ID."""
    return ''.join(random.choices(string.digits, k=10))


# Create your models here.


# Restaurant Model
class Restaurant(models.Model):
    objects: models.Manager['Restaurant']
    DoesNotExist: type[Exception]
    restaurantid = models.AutoField(primary_key=True)
    owner = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, default="Restaurant Name")
    address = models.CharField(max_length=255, default="Address")
    contact = models.CharField(max_length=20, default="Contact Number")
    email = models.EmailField(default="project1878@gmail.com")
    website = models.CharField(max_length=255, blank=True, null=True)
    rating = models.FloatField(default=0.0)
    created_on = models.DateTimeField(auto_now_add=True)

    latitude = models.TextField(default="*")
    longitude = models.TextField(default="*")

    baseimg = models.TextField(default="*")

    def __str__(self):
        return f"{self.restaurantid} : {self.name} - {self.owner.username} - {self.rating}"


# Product Model
class Product(models.Model):
    prodid = models.AutoField(primary_key=True)

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    metadata = models.TextField(default="*")
    price = models.FloatField()
    image = models.TextField(default="*")
    createdon = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.prodid} - RestName: {self.restaurant.name} - ProductName: {self.name} - Cat: {self.category} - Rs.{self.price} - {self.createdon}"


# Transaction Model
class Transaction(models.Model):
    tid = models.AutoField(primary_key=True)

    # 10-digit unique ID for tracking
    transaction_id = models.CharField(max_length=10,
                                      unique=True,
                                      default=generate_transaction_id)

    restaurantname = models.TextField(default="*")

    customername = models.CharField(max_length=255)
    custmoreid = models.TextField(default="*")

    dishdetails = models.TextField(default="*")
    gotcreditscore = models.TextField(default="*")
    billamount = models.FloatField()

    discountamount = models.FloatField(default=0.0)
    createdon = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customername} - {self.restaurantname} - ₹{self.billamount} - ID:{self.transaction_id}"


# Product Cart Model
class CartDetails(models.Model):
    cartid = models.AutoField(primary_key=True)

    restaurantname = models.TextField(default="*")
    productname = models.TextField(default="*")
    username = models.TextField(default="*")
    productprice = models.FloatField()  # Change this to FloatField
    productimage = models.TextField(
        default="*")  # Add product image field (optional)
    quantity = models.IntegerField(default=1)  # Add quantity field
    extradetails = models.TextField(default="*")
    status = models.TextField(default="new")

    createdon = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.cartid} - {self.productname} - ₹{self.productprice} - {self.extradetails} - {self.status}"

    def total_price(self):
        return self.productprice * self.quantity  # Calculate total price based on quantity


# Restaurant Gallery
class RestGallery(models.Model):
    galleryid = models.AutoField(primary_key=True)

    restaurantid = models.TextField(default="*")
    restaurantname = models.TextField(default="*")
    title = models.TextField(default="*")
    baseimg = models.TextField(default="*")

    createdon = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.galleryid} - {self.restaurantname} - {self.title} - {self.createdon}"


# Restaurant Feedback
class RestFeedback(models.Model):
    feedbackid = models.AutoField(primary_key=True)

    restaurantid = models.TextField(default="*")
    restaurantname = models.TextField(default="*")
    feedback = models.TextField(default="*")
    emotion = models.TextField(default="*")

    createdon = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.feedbackid} - {self.restaurantname} - {self.feedback} - {self.emotion} - {self.createdon}"


# Restaurant Sale
class RestSale(models.Model):
    saleid = models.AutoField(primary_key=True)

    restaurantid = models.TextField(default="*")
    restaurantname = models.TextField(default="*")

    startdate = models.TextField(default="*")
    enddate = models.TextField(default="*")

    status = models.TextField(default="*")  # incoming/active/closed

    title = models.TextField(default="*")
    description = models.TextField(default="*")
    baseimg = models.TextField(default="*")

    createdon = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.saleid} - {self.restaurantname} - {self.title} - Sale from {self.startdate} to {self.enddate}"


#$ Customer


class CustomerData(models.Model):
    cid = models.AutoField(primary_key=True)
    username = models.OneToOneField(User, on_delete=models.CASCADE)
    password = models.CharField(max_length=255, default="******")
    contact = models.CharField(max_length=20, default="1111111111")
    email = models.EmailField(unique=True, default="project1878@gmail.com")
    baseimg = models.TextField(default="*")

    address = models.TextField(default="*")

    latitude = models.TextField(default="*")
    longitude = models.TextField(default="*")

    createdon = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.cid} : {self.username} - {self.address} - {self.contact}"


# Customer Restaurant Credits:
class CustomerCreditsData(models.Model):
    ccid = models.AutoField(primary_key=True)
    username = models.OneToOneField(User, on_delete=models.CASCADE)
    creditscore = models.FloatField(default=0.0)  # Change this to FloatField
    createdon = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ccid} : {self.username} - {self.creditscore}"


class Chatbot(models.Model):
    cbid = models.AutoField(primary_key=True)
    username = models.TextField(default="*")

    query = models.TextField(default="*")
    response = models.TextField(default="*")

    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.cbid} - {self.query}"


"""

class RestaurantData(models.Model):
    rid         = models.AutoField(primary_key=True)

    mainname    = models.CharField(max_length=255, default="empty")

    mainaddress = models.CharField(max_length=255, default="empty")
    maincontact = models.CharField(max_length=255, default="empty")
    mainemail   = models.CharField(max_length=255, default="empty")
    mainwebsite = models.CharField(max_length=255, default="empty")
    mainlat     = models.CharField(max_length=255, default="empty")
    mainlong    = models.CharField(max_length=255, default="empty")
    openingdate = models.CharField(max_length=255, default="empty")


    def __str__(self):
        return f"{self.mainname} - {self.openingdate}"


class FranchiseData(models.Model):
    fid         = models.AutoField(primary_key=True)


    refrid      = models.IntegerField(default=0)
    fname       = models.CharField(max_length=255, default="empty")

    faddress    = models.CharField(max_length=255, default="empty")
    fcontact    = models.CharField(max_length=255, default="empty")
    femail      = models.CharField(max_length=255, default="empty")
    fwebsite    = models.CharField(max_length=255, default="empty")
    flat        = models.CharField(max_length=255, default="empty")
    flong       = models.CharField(max_length=255, default="empty")
    openingdate = models.CharField(max_length=255, default="empty")

    ratings     = models.FloatField(default=0.0)

    details     = models.TextField(default="empty") 


    def __str__(self):
        return f"{self.fname} - {self.openingdate}"

class FranchiseFeedBackData(models.Model):
    ffbid         = models.AutoField(primary_key=True)

    refrid      = models.IntegerField(default=0)
    reffid      = models.IntegerField(default=0)
    fname       = models.CharField(max_length=255, default="empty")

    createdon   = models.CharField(max_length=255, default="empty")

    feedback    = models.TextField(default="empty") 

    def __str__(self):
        return f"{self.fname} - {self.openingdate}"

class CustomerCreditData(models.Model):
    ccid        = models.AutoField(primary_key=True)

    refrid      = models.IntegerField(default=0)
    reffid      = models.IntegerField(default=0)
    refcid      = models.IntegerField(default=0)

    cname       = models.CharField(max_length=255, default="empty")

    creditamount= models.IntegerField(default=0)

    createdon   = models.CharField(max_length=255, default="empty")

    def __str__(self):
        return f"{self.ccid} - {self.cname} - {self.creditamount} -  {self.createdon}"



class CustomerData(models.Model):
    cid         = models.AutoField(primary_key=True)

    cname       = models.CharField(max_length=255, default="empty")

    caddress    = models.CharField(max_length=255, default="empty")
    ccontact    = models.CharField(max_length=255, default="empty")
    cemail      = models.CharField(max_length=255, default="empty")
    caadharno   = models.CharField(max_length=255, default="empty")
    createdon   = models.CharField(max_length=255, default="empty")

    balance     = models.IntegerField(default=0)




    def __str__(self):
        return f"id:{self.cid} - Name:{self.cname} - {self.createdon}"


class TransactionData(models.Model):
    tid         = models.AutoField(primary_key=True)

    reffid      = models.IntegerField(default=0)
    refcid      = models.IntegerField(default=0)

    cname       = models.CharField(max_length=255, default="empty")

    dishdetails = models.TextField(default="empty")

    bill        = models.IntegerField(default=0)
    discountamt = models.IntegerField(default=0)

    createdon   = models.CharField(max_length=255, default="empty")

    def __str__(self):
        return f"id:{self.tid} - name:{self.cname} - bill:{self.bill} - discountamt:{self.discountamt} - {self.createdon}"








"""

# class SensorData(models.Model):
#     # api_key = models.CharField(max_length=300)
#     nodename = models.CharField(max_length=255)
#     depth_1 = models.FloatField(default=0.0)
#     depth_2 = models.FloatField(default=0.0)
#     depth_3 = models.FloatField(default=0.0)
#     temperature = models.FloatField(default=0.0)
#     humidity = models.FloatField(default=0.0)
#     timestamp = models.DateTimeField(auto_now_add=True)

#     # mode = models.CharField(max_length=10)

#     def __str__(self):
#         return f"{self.nodename} - {self.timestamp}"

# class Nodedata(models.Model):
#     user_name = models.CharField(max_length=255, default="")
#     node_name = models.CharField(max_length=255, default="")
#     Loc_lat = models.CharField(max_length=20, default="")
#     Loc_long = models.CharField(max_length=20, default="")
#     api_key = models.CharField(max_length=300, default="")

#     def __str__(self):
#         return f"{self.user_name} - {self.node_name}"

# class Clusterdata(models.Model):
#     user_name = models.CharField(max_length=255, default="")
#     cluster_name = models.CharField(max_length=255, default="")
#     clust_data = models.CharField(max_length=500, default="")

#     def __str__(self):
#         return f"{self.user_name} - {self.cluster_name}"

# ------------------------------------
# Sample Code Below
# ------------------------------------

# class Product(models.Model):
#     Product_id = models.AutoField(primary_key=True)
#     product_name = models.CharField(max_length=50)
#     category = models.CharField(max_length=50, default="")
#     slug = models.CharField(max_length=100, default="")
#     price = models.IntegerField(default=0)
#     desc = models.CharField(max_length=300)
#     image = models.ImageField(upload_to="tze/images", default="")
#     testimoniallink = models.CharField(max_length=300, default="")
#     ytlink = models.CharField(max_length=300, default="")
#     benifits = models.CharField(max_length=300, default="")
#     how_to_use = models.CharField(max_length=400, default="")
#     doc_link = models.CharField(max_length=300, default="")
#     net_Qty = models.CharField(max_length=100, default="")
#     pack_of = models.CharField(max_length=50, default="")
#     # pub_date = models.DateField()
#     # subcategory = models.CharField(max_length=30, default="")

#     def __str__(self):
#         return self.product_name

# # mem: member
# class Contact(models.Model):
#     mem_id = models.AutoField(primary_key=True)

#     mem_name = models.CharField(max_length=60, default="")
#     mem_image = models.ImageField(upload_to="tze/contactImages", default="")
#     mem_desc = models.CharField(max_length=300, default="")
#     mem_email = models.CharField(max_length=100, default="")
#     mem_phone = models.IntegerField(default=0)
#     mem_fb_link = models.CharField(max_length=100, default="")
#     mem_IG_link = models.CharField(max_length=100, default="")
#     mem_status = models.CharField(max_length=100, default="")
#     mem_tag = models.CharField(max_length=20, default="")

#     def __str__(self):
#         return self.mem_name

# class Contact(models.Model):
#     msg_id = models.AutoField(primary_key=True)

#     name = models.CharField(max_length=50, default="")
#     email = models.CharField(max_length=70, default="")
#     phone = models.IntegerField(default=0)
#     msg = models.CharField(max_length=500, default="")

#     def __str__(self):
#         return self.name
