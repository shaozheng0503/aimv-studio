class ModelRouter:
    """Routes generation requests to the best model based on style, quality, and budget."""

    VIDEO_STYLE_MAP = {
        "韩娱": "seedance",
        "国风": "veo",
        "独立电影": "veo",
        "赛博朋克": "grok",
        "幻想童话": "grok",
        "复古迪斯科": "seedance",
        "都市甜酷": "grok",
    }

    def route_video(self, style: str, quality: str = "high", budget: str = "cloud") -> str:
        if budget == "local":
            return "wan2.2"
        return self.VIDEO_STYLE_MAP.get(style, "veo")

    def route_music(self, needs_vocal: bool, style: str, quality: str = "high") -> str:
        if needs_vocal and style in ("流行", "韩娱", "嘻哈", "pop", "kpop"):
            return "suno"
        if quality == "studio" or style in ("古典", "国风", "电影配乐"):
            return "lyria"
        return "acestep"
