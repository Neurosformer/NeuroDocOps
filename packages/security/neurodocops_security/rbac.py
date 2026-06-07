from __future__ import annotations

from enum import Enum
from typing import Mapping

from pydantic import BaseModel, Field


class AccessDeniedError(RuntimeError):
    """Raised when an actor lacks the requested permission."""


class Role(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    REVIEWER = "reviewer"
    AUDITOR = "auditor"
    INTEGRATION = "integration"


class Permission(str, Enum):
    PACKET_CREATE = "packet:create"
    PACKET_READ = "packet:read"
    DOCUMENT_UPLOAD = "document:upload"
    PACKET_PROCESS = "packet:process"
    REVIEW_COMPLETE = "review:complete"
    REVIEW_TASK_READ = "review_task:read"
    REVIEW_TASK_UPDATE = "review_task:update"
    EXPORT_PACKET = "export:packet"
    AUDIT_READ = "audit:read"
    JOB_READ = "job:read"


class ActorContext(BaseModel):
    actor_id: str = Field(default="dev-admin", min_length=1)
    role: Role = Role.ADMIN


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),
    Role.MANAGER: {
        Permission.PACKET_CREATE,
        Permission.PACKET_READ,
        Permission.DOCUMENT_UPLOAD,
        Permission.PACKET_PROCESS,
        Permission.REVIEW_COMPLETE,
        Permission.REVIEW_TASK_READ,
        Permission.REVIEW_TASK_UPDATE,
        Permission.EXPORT_PACKET,
        Permission.AUDIT_READ,
        Permission.JOB_READ,
    },
    Role.REVIEWER: {
        Permission.PACKET_CREATE,
        Permission.PACKET_READ,
        Permission.DOCUMENT_UPLOAD,
        Permission.PACKET_PROCESS,
        Permission.REVIEW_COMPLETE,
        Permission.REVIEW_TASK_READ,
        Permission.REVIEW_TASK_UPDATE,
        Permission.AUDIT_READ,
        Permission.JOB_READ,
    },
    Role.AUDITOR: {
        Permission.PACKET_READ,
        Permission.REVIEW_TASK_READ,
        Permission.AUDIT_READ,
        Permission.JOB_READ,
    },
    Role.INTEGRATION: {
        Permission.PACKET_CREATE,
        Permission.PACKET_READ,
        Permission.DOCUMENT_UPLOAD,
        Permission.PACKET_PROCESS,
        Permission.EXPORT_PACKET,
        Permission.JOB_READ,
    },
}


def actor_from_headers(headers: Mapping[str, str]) -> ActorContext:
    actor_id = headers.get("x-actor") or headers.get("X-Actor") or "dev-admin"
    role_value = headers.get("x-role") or headers.get("X-Role") or Role.ADMIN.value
    try:
        role = Role(role_value.strip().lower())
    except ValueError as exc:
        valid = ", ".join(role.value for role in Role)
        raise AccessDeniedError(f"Unsupported role '{role_value}'. Supported roles: {valid}.") from exc
    return ActorContext(actor_id=actor_id, role=role)


def has_permission(actor: ActorContext, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[actor.role]


def require_permission(actor: ActorContext, permission: Permission) -> None:
    if not has_permission(actor, permission):
        raise AccessDeniedError(f"Actor '{actor.actor_id}' with role '{actor.role.value}' lacks permission '{permission.value}'.")
