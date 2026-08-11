from __future__ import annotations

from typing import Any

from fastapi import Request

from farebeacon.api.schemas import ApiResponse, ResponseMeta


def success(request: Request, data: Any) -> ApiResponse[Any]:
    return ApiResponse(data=data, meta=ResponseMeta(request_id=request.state.request_id))
