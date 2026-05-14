from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


def set_flash(request: Request, message: str, msg_type: str = "success") -> None:
    request.session["flash"] = {"message": message, "type": msg_type}


class FlashMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        flash = request.session.pop("flash", None)
        request.state.flash = flash
        return await call_next(request)
