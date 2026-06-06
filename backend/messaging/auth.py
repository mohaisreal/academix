from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken


User = get_user_model()


class JwtQueryStringAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    def __call__(self, scope):
        return JwtQueryStringAuthMiddlewareInstance(scope, self.inner)


class JwtQueryStringAuthMiddlewareInstance:
    def __init__(self, scope, inner):
        self.scope = scope
        self.inner = inner

    async def __call__(self, receive, send):
        scope = dict(self.scope)
        token = self._get_token(scope.get('query_string', b''))
        scope['user'] = await self._get_user(token)
        inner = self.inner(scope)
        return await inner(receive, send)

    def _get_token(self, query_string):
        params = parse_qs(query_string.decode('utf-8'))
        token = params.get('token', [None])[0]
        return token

    async def _get_user(self, token):
        if not token:
            return AnonymousUser()
        try:
            access_token = AccessToken(token)
            user_id = access_token.get('user_id')
            return await User.objects.aget(pk=user_id)
        except Exception:
            return AnonymousUser()


def JwtQueryStringAuthMiddlewareStack(inner):
    from channels.auth import AuthMiddlewareStack
    return JwtQueryStringAuthMiddleware(AuthMiddlewareStack(inner))
