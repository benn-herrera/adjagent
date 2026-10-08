"""The qwen3 family."""

from adjagent.family import Family

FAMILY = Family(
    "qwen3",
    {
        "highest": "Qwen3.8-Flash-Next",
        "high": "Qwen3.8-Flash-Next",
        "medium": "Qwen3.8-27B",
        "low": "Qwen3.6-35B-A3B",
        "lowest": "Qwen3.5-9B",
    },
)
