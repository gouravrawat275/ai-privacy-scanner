import jwt
from datetime import datetime, timedelta, timezone


class WrongTokenTypeError(jwt.PyJWTError):
    pass


def _create_token(username, config, token_type, expires_delta):
    api_cfg = config["api"]
    payload = {
        "sub": username,
        "type": token_type,
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    return jwt.encode(payload, api_cfg["secret_key"], algorithm=api_cfg.get("algorithm", "HS256"))


def create_access_token(username, config):
    minutes = config["api"].get("token_expiry_minutes", 60)
    return _create_token(username, config, "access", timedelta(minutes=minutes))


def create_refresh_token(username, config):
    days = config["api"].get("refresh_token_expiry_days", 30)
    return _create_token(username, config, "refresh", timedelta(days=days))


def decode_token(token, config, expected_type):
    api_cfg = config["api"]
    payload = jwt.decode(token, api_cfg["secret_key"], algorithms=[api_cfg.get("algorithm", "HS256")])
    if payload.get("type") != expected_type:
        raise WrongTokenTypeError(f"expected a {expected_type!r} token, got {payload.get('type')!r}")
    return payload["sub"]
