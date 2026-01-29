import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import boto3
import jwt
from botocore.config import Config


def use_mcp() -> bool:
    value = os.getenv("USE_MCP", "").strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def _load_registry() -> Dict[str, Any]:
    raw = os.getenv("MCP_REGISTRY_JSON", "{}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


class SecretManager:
    @staticmethod
    def get_secret(name: str, region: str) -> Dict[str, Any]:
        respuesta: Dict[str, Any] = {}
        try:
            session = boto3.session.Session()
            config = Config(region_name=region, connect_timeout=3, read_timeout=3)
            client = session.client(
                service_name="secretsmanager", region_name=region, config=config
            )
            get_secret_value_response = client.get_secret_value(SecretId=name)
            if "SecretString" in get_secret_value_response:
                secret = get_secret_value_response["SecretString"]
            else:
                secret = get_secret_value_response["SecretBinary"]
            respuesta["code"] = "OK"
            respuesta["secreto"] = json.loads(secret)
            return respuesta
        except Exception as exc:
            respuesta["code"] = "NOK"
            respuesta["error_message"] = "Error al obtener secreto"
            respuesta["error_technical"] = str(exc)
            return respuesta


def _get_private_key(config: Dict[str, Any]) -> str:
    if config.get("private_key"):
        return str(config["private_key"])
    secret_name = config.get("secret_name", "")
    if not secret_name:
        return ""
    region = os.getenv("AWS_REGION", "us-east-1")
    secret_response = SecretManager.get_secret(secret_name, region)
    if secret_response.get("code") == "OK":
        return str(secret_response["secreto"].get("private_key", ""))
    return ""


def _generate_mcp_jwt(
    agent_name: str, config: Dict[str, Any], session_id: str, ubicaciones: List[Any]
) -> str:
    private_key = _get_private_key(config)
    if not private_key:
        raise ValueError("MCP private key no disponible")
    payload = {
        "sub": session_id or "unknown",
        "agentes": [agent_name],
        "ubicaciones": ubicaciones or [],
        "exp": datetime.now() + timedelta(hours=1),
        "iat": datetime.now(),
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def build_mcp_clients(
    session_id: str, ubicaciones: List[Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    registry = _load_registry()
    servers: List[Dict[str, Any]] = []
    tools: List[Dict[str, Any]] = []
    for name, config in registry.items():
        url = str(config.get("url", "")).strip()
        if not url:
            continue
        try:
            token = _generate_mcp_jwt(name, config, session_id, ubicaciones)
            server_name = f"{name}-mcp"
            servers.append(
                {
                    "type": "url",
                    "url": url,
                    "name": server_name,
                    "authorization_token": token,
                }
            )
            tools.append({"type": "mcp_toolset", "mcp_server_name": server_name})
        except Exception as exc:
            print(f"Error configurando MCP para {name}: {exc}")
    return servers, tools
