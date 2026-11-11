"""Error reports (emails to ADMINS) must not carry what people typed: birth data, answers, email codes."""

from django.views.debug import SafeExceptionReporterFilter


class PrivateReporterFilter(SafeExceptionReporterFilter):
    def get_post_parameters(self, request):
        if request is None:
            return {}
        return {key: self.cleansed_substitute for key in request.POST}
