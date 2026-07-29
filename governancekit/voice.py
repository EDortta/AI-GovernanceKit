"""Optional AI-ListenToMeOnCLI integration detection."""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class VoiceIntegrationStatus:
    status: str
    command: str | None
    config_hint: str | None
    message: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


_VOICE_BIN_CANDIDATES = (
    "ai-listentomeoncli",
    "AI-ListenToMeOnCLI",
    "aitalk",
)


def detect_voice_integration(root: Path) -> VoiceIntegrationStatus:
    env_bin = os.environ.get("AI_LISTENTOMEONCLI_BIN", "").strip()
    candidates = [env_bin] if env_bin else []
    candidates.extend(_VOICE_BIN_CANDIDATES)

    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return VoiceIntegrationStatus(
                status="available",
                command=resolved,
                config_hint="Do not read secrets aloud; keep approval prompts textual for sensitive actions.",
                message=f"voice integration available via {Path(resolved).name}",
            )

    return VoiceIntegrationStatus(
        status="absent",
        command=None,
        config_hint="Set AI_LISTENTOMEONCLI_BIN or install AI-ListenToMeOnCLI to enable optional voice prompts.",
        message="optional voice integration not detected",
    )


def format_voice_integration(status: VoiceIntegrationStatus) -> str:
    lines = ["AI GovernanceKit voice-integration"]
    lines.append(f"status: {status.status}")
    lines.append(f"command: {status.command or '(not found)'}")
    if status.config_hint:
        lines.append(f"hint: {status.config_hint}")
    lines.append(f"message: {status.message}")
    return "\n".join(lines)
