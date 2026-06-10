from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.tokens import AccessToken


User = get_user_model()


class JwtQueryStringAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        token = self._get_token(scope.get('query_string', b''))
        scope['user'] = await self._get_user(token)
        return await super().__call__(scope, receive, send)

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
