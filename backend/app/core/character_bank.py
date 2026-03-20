"""CharacterBank — Maintains character identity consistency across MV shots.

Stores structured character profiles (appearance, outfit, style) and automatically
appends character descriptions to generation prompts, ensuring visual coherence.
"""

from dataclasses import dataclass, field, asdict


@dataclass
class CharacterProfile:
    name: str
    role: str = "main"  # main / supporting / extra
    reference_images: list[str] = field(default_factory=list)
    appearance: dict = field(default_factory=dict)
    # e.g. {"face": "oval", "hair": "long black", "skin": "fair", "age": "20s"}
    outfit: dict = field(default_factory=dict)
    # e.g. {"top": "white crop top", "bottom": "denim shorts", "accessories": "silver earrings"}
    style_tags: list[str] = field(default_factory=list)
    # e.g. ["kpop", "practice_room", "dance"]

    def to_prompt_suffix(self) -> str:
        """Generate a prompt suffix describing this character for image/video generation."""
        parts = []
        if self.appearance:
            app = ", ".join(f"{k}: {v}" for k, v in self.appearance.items())
            parts.append(f"Character appearance: {app}")
        if self.outfit:
            out = ", ".join(f"{k}: {v}" for k, v in self.outfit.items())
            parts.append(f"Wearing: {out}")
        if self.style_tags:
            parts.append(f"Style: {', '.join(self.style_tags)}")
        return ". ".join(parts)


class CharacterBank:
    def __init__(self, data: dict | None = None):
        self.characters: dict[str, CharacterProfile] = {}
        if data:
            self.load(data)

    def add_character(self, profile: CharacterProfile):
        self.characters[profile.name] = profile

    def get(self, name: str) -> CharacterProfile | None:
        return self.characters.get(name)

    def get_prompt_suffix(self, character_name: str) -> str:
        """Get prompt suffix for a specific character."""
        char = self.get(character_name)
        if not char:
            return ""
        return char.to_prompt_suffix()

    def enrich_prompt(self, prompt: str, character_name: str) -> str:
        """Append character description to any generation prompt."""
        suffix = self.get_prompt_suffix(character_name)
        if suffix:
            return f"{prompt}. {suffix}"
        return prompt

    def get_reference_images(self, character_name: str) -> list[str]:
        """Get reference images for frame-chaining and image-prompt consistency."""
        char = self.get(character_name)
        return char.reference_images if char else []

    def to_dict(self) -> dict:
        return {name: asdict(profile) for name, profile in self.characters.items()}

    def load(self, data: dict):
        valid_fields = {f.name for f in CharacterProfile.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        for name, profile_data in data.items():
            if not isinstance(profile_data, dict):
                continue
            # Strip unknown fields so CrewAI extra output doesn't cause TypeError
            filtered = {k: v for k, v in profile_data.items() if k in valid_fields}
            filtered.setdefault("name", name)
            self.characters[name] = CharacterProfile(**filtered)
