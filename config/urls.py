from django.contrib import admin
from django.urls import include, path

urlpatterns = [path("staff/", admin.site.urls), path("", include("apps.web.urls"))]

handler404 = "apps.web.views.not_found"
handler500 = "apps.web.views.server_error"
