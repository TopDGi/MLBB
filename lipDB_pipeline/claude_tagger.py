import anthropic
import base64
import json
import re

# 시스템 프롬프트는 모든 호출에 공통 — cache_control로 캐싱해 비용 절감
_SYSTEM_PROMPT = """You are a Korean beauty color expert specializing in lipstick tone classification.
Analyze the lipstick swatch image and classify it. Respond ONLY with valid JSON — no markdown, no extra text.

Output format:
{"undertone_tag": "warm|cool|neutral", "season_tone": "warm_mute|warm_bright|cool_mute|cool_bright|autumn_mute", "hex_estimate": "#RRGGBB"}

Tone definitions:
- warm_mute: earthy, peachy, brick, terracotta — low saturation, warm undertone
- warm_bright: coral, orange-red, vivid tomato — high saturation, warm undertone
- cool_mute: mauve, rosewood, dusty rose, muted pink — low saturation, cool undertone
- cool_bright: berry, fuchsia, magenta, blue-red — high saturation, cool undertone
- autumn_mute: deep terracotta, rust, brown-red, burgundy — muted dark warm

hex_estimate: your best estimate of the swatch color as a hex code."""

_client = anthropic.Anthropic()


def tag_swatch(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """
    스와치 이미지를 Claude Vision API로 분석해 톤 태그 반환.

    Returns:
        {"undertone_tag": str, "season_tone": str, "hex_estimate": str}

    비용 절감: 시스템 프롬프트에 cache_control 적용.
    대량 처리 시 claude-haiku-4-5로 교체하면 비용을 ~80% 절감할 수 있음.
    """
    b64_data = base64.standard_b64encode(image_bytes).decode()

    response = _client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=256,
        system=[{
            "type": "text",
            "text": _SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},  # 반복 호출 시 캐시 히트
        }],
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64_data,
                    },
                },
                {"type": "text", "text": "Classify this lipstick swatch."},
            ],
        }],
    )

    raw = response.content[0].text.strip()
    # 마크다운 코드블록 제거 (Claude가 간혹 감쌀 수 있음)
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)


def detect_media_type(url: str, content_type_header: str = "") -> str:
    """URL 확장자 또는 Content-Type 헤더로 미디어 타입 결정."""
    if "webp" in content_type_header or url.lower().endswith(".webp"):
        return "image/webp"
    if "png" in content_type_header or url.lower().endswith(".png"):
        return "image/png"
    if "gif" in content_type_header or url.lower().endswith(".gif"):
        return "image/gif"
    return "image/jpeg"  # 올리브영 기본값
