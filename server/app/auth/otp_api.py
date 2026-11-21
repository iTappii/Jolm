from ipaddress import IPv6Address, ip_address
from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from app.auth import email, otp, sms
from app.auth.sessions import Tokens
from app.i18n import pick_locale

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class OtpRequest(BaseModel):
    channel: Literal["email", "phone"]
    destination: str = Field(min_length=1, max_length=320)

    def normalized_destination(self) -> str:
        if self.channel == "email":
            return email.normalize_email(self.destination)
        return sms.normalize_phone(self.destination)


class OtpVerifyRequest(OtpRequest):
    code: str = Field(pattern=r"^[0-9]{6}$")


def _client_ip(request: Request) -> str:
    try:
        address = ip_address(request.client.host) if request.client else None
    except ValueError:
        return "unknown"
    if isinstance(address, IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return str(address) if address is not None else "unknown"


@router.post("/otp/request", status_code=204)
async def request_code(payload: OtpRequest, request: Request) -> Response:
    destination = payload.normalized_destination()
    if payload.channel == "email":
        provider = email.get_email_provider()
    else:
        provider = sms.get_sms_provider()
    await otp.issue(
        request.app.state.db, provider, payload.channel, destination, _client_ip(request)
    )
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.post("/otp/verify")
async def verify_code(payload: OtpVerifyRequest, request: Request, response: Response) -> Tokens:
    response.headers["Cache-Control"] = "no-store"
    return await otp.verify(
        request.app.state.db,
        payload.channel,
        payload.normalized_destination(),
        payload.code,
        pick_locale(request.headers.get("accept-language")),
    )
