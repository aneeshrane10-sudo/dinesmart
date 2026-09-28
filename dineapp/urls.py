from django.urls import path
from . import views
from . import cv_views

urlpatterns = [

    # $$$Client side:

    path("", views.welcome, name="welcome"),
    path("menu/", views.menu, name="menu"),
    path("search/", views.search, name="search"),
    path("products/", views.products, name="products"),

    path('notifications/', views.notifications, name='notifications'),



    path('profile/', views.profile, name='profile'),
    path('qrscanner/', views.qrscanner, name='qrscanner'),
    # path('cart/', views.cart, name='cart'),
    path('meonmap/', views.meOnMap, name='meonmap'),

    path('addtocart/<int:product_id>/', views.addtocart, name='addtocart'),


    path('viewcart/', views.viewcart, name='viewcart'),
    path('updatecart/', views.update_cart, name='update_cart'),
    # path('payment/', views.payment_page, name='payment_page'),
    path('stripepayment/', views.stripepayment, name='stripepayment'),

    path('processpayment/', views.process_payment, name='process_payment'),  # POST Request
    path('successpaymentpage/', views.successpaymentpage, name='successpaymentpage'),  # POST Request



    path("transaction/", views.transaction, name="transaction"),
    path("meonmap/", views.meonmap, name="meonmap"),

    path("chatbot/", views.chatbot, name="chatbot"),



    path('user_register/', views.user_register, name='user_register'),
    path('user_login/', views.user_login, name='user_login'),
    path('user_logout/', views.user_logout, name='user_logout'),



    path('category/<str:categoryName>/', views.categoryProducts, name='categoryProducts'),




    # $$$Restaurant side:
    path('restpublicprofile/<int:restaurant_id>/', views.restpublicprofile, name='restpublicprofile'),
    path('productdetails/<int:prodid>/', views.productdetails, name='productdetails'),

    # Authentication
    path('restaurantregister/', views.restaurantregister, name='restaurantregister'),
    path('restaurantlogin/', views.restaurantlogin, name='restaurantlogin'),
    path('restaurantlogout/', views.restaurantlogout, name='restaurantlogout'),

    # Dashboard & Profile
    path('restaurantdashboard/', views.restaurantdashboard, name='restaurantdashboard'),
    path('restaurantprofile/', views.restaurantprofile, name='restaurantprofile'),

    path('restaurant/gallery/', views.restaurantGallery, name='restaurantGallery'),
    path('restaurant/gallery/delete/<int:gallery_id>/', views.restaurantGalleryDelete, name='restaurantGalleryDelete'),

    path('restaurantfeedback/', views.restaurantfeedback, name='restaurantfeedback'),


    path('restaurantsales/', views.restaurantsales, name='restaurantsales'),
    path('restaurantsalesadd', views.restaurantsalesadd, name='restaurantsalesadd'),
    path('restaurantsalesedit/<int:sale_id>/', views.restaurantsalesedit, name='restaurantsalesedit'),

    path('submitFeedback/', views.submitFeedback, name='submit_feedback'),


    # Products
    path('restaurantallproducts/', views.restaurantallproducts, name='restaurantallproducts'),
    path('restaurantaddproduct/', views.restaurantaddproduct, name='restaurantaddproduct'),
    path('restauranteditproduct/<int:product_id>/', views.restauranteditproduct, name='restauranteditproduct'),
    path('restaurantdeleteproduct/<int:product_id>/', views.restaurantDeleteProduct, name='restaurantdeleteproduct'),


    # Transactions
    path('restauranttransactions/', views.restauranttransactions, name='restauranttransactions'),





    # ─── CV Occupancy Detection System ───────────────────────────────────────
    path('occupancy/dashboard/', cv_views.occupancy_dashboard, name='occupancy_dashboard'),
    path('occupancy/calibrate/', cv_views.zone_calibrator, name='zone_calibrator'),
    path('occupancy/calibrate/save/', cv_views.save_zones, name='save_zones'),
    path('occupancy/upload-frame/', cv_views.upload_camera_frame, name='upload_camera_frame'),
    path('occupancy/start/', cv_views.start_detection, name='start_detection'),
    path('occupancy/stop/', cv_views.stop_detection, name='stop_detection'),

    # REST API endpoints
    path('api/occupancy/status/', cv_views.api_occupancy_status, name='api_occupancy_status'),
    path('api/occupancy/analytics/', cv_views.api_occupancy_analytics, name='api_occupancy_analytics'),
    path('api/occupancy/heatmap/', cv_views.api_occupancy_heatmap, name='api_occupancy_heatmap'),

    # path("viewNodes/", views.viewNodes, name="viewNodes"),
    # path("viewNodeData/", views.viewNodeData, name="viewNodeData"),
    # path("viewclusterData/", views.viewclusterData, name="viewclusterData"),
    # path("addnode/", views.addnode, name="addnode"),
    # path("addcluster/", views.addcluster, name="addcluster"),


    # path('user_login/', views.user_login, name='user_login'),
    # path('user_logout/', views.user_logout, name='user_logout'),
    # path('user_register/', views.user_register, name='user_register'),

    # path('sensor_data/', views.sensor_data, name='sensor_data'),
    # path('read_sensor_data/', views.read_sensor_data, name='read_sensor_data'),
    # path('apikeyGen/', views.your_view_function, name='your_view_function'),

    # path("contact/", views.contact, name="ContactUs"),
    # # path("products/<int:myid>", views.productView, name="ProductView"),
    # path("products/<str:myslug>", views.productView, name="ProductView"),
]
