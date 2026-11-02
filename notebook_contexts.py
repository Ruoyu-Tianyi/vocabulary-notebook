"""Immutable notebook context identities; ordinary notebook names remain descriptive only.

The reserved ID prefix carries the preset through existing v1 sync/export fields.
Older clients can still read these books as ordinary notebooks (without context AI).
"""
import re
import uuid

PRESETS = {
    "finance": {"label": "金融", "prompt": "Interpret the word in finance, investment and accounting. Prioritize established financial senses and use a realistic financial example."},
    "law": {"label": "法律", "prompt": "Interpret the word in legal study, contracts and legal proceedings. Prioritize established legal senses and use a realistic legal example."},
    "medicine": {"label": "医药", "prompt": "Interpret the word in medicine, pharmacy and clinical study. Prioritize established medical senses and use a realistic medical example, not treatment advice."},
}


def context_id(notebook_id):
    match = re.fullmatch(r"ctx-(finance|law|medicine)-[0-9a-f]{12}", notebook_id or "")
    return match[1] if match else ""


def new_id(preset=""):
    suffix = uuid.uuid4().hex[:12]
    return f"ctx-{preset}-{suffix}" if preset else suffix


def prompt_for(notebook_id):
    preset = PRESETS.get(context_id(notebook_id))
    if not preset:
        return ""
    return (preset["prompt"] + " Keep the required JSON structure, Chinese definitions and English example. "
            "If no specialized sense exists, give the ordinary meaning in a relevant context. "
            "Do not invent a specialized meaning or accept invalid spelling just to fit the domain.")
