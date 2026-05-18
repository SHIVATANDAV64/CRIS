from fastapi import APIRouter

from config.settings import get_config, update_config, reset_config
from server.models.schemas import SettingsUpdate

router = APIRouter(tags=["Settings & Models"])


@router.get("/api/models")
async def list_models():
    """List available models for the model selector."""
    return {
        "models": [
            {
                "id": "darwin-opus",
                "name": "Darwin-36B-Opus",
                "provider": "Modal",
                "description": "Fine-tuned Qwen3.6-35B-A3B for research reasoning",
            },
            {
                "id": "minimax-m2.5",
                "name": "MiniMax M2.5",
                "provider": "Bedrock",
                "description": "AWS Bedrock hosted MiniMax model",
            },
        ],
        "default": "darwin-opus",
    }


@router.get("/api/settings")
async def get_settings():
    """Get current configuration."""
    config = get_config()
    return {"config": config}


@router.post("/api/settings")
async def update_settings_route(req: SettingsUpdate):
    """Update configuration."""
    config = update_config(req.updates)
    return {"config": config}


@router.post("/api/settings/reset")
async def reset_settings_route():
    """Reset configuration to defaults."""
    config = reset_config()
    return {"config": config}
