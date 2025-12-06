# core/middleware.py
from django.utils import timezone

class UserTimezoneMiddleware:
    """
    Activate the timezone stored in the user's session.

    - We store the selected timezone in request.session["django_timezone"]
      from the settings page.
    - If present, activate it for this request.
    - Otherwise, fall back to default settings.TIME_ZONE.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tzname = request.session.get("django_timezone")

        if tzname:
            try:
                timezone.activate(tzname)
            except Exception:
                # If invalid timezone string somehow got into the session,
                # fall back to global default.
                timezone.deactivate()
        else:
            timezone.deactivate()

        response = self.get_response(request)
        return response
