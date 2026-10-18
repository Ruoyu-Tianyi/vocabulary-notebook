from fastapi.testclient import TestClient as BaseClient


class TestClient(BaseClient):
    __test__ = False

    def __init__(self, app, *, peer="127.0.0.1", **kwargs):
        async def socket_peer(scope, receive, send):
            scope = dict(scope, client=(peer, 43210))
            await app(scope, receive, send)
        super().__init__(socket_peer, **kwargs)
