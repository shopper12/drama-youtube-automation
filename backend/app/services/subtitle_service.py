from pathlib import Path


def _timestamp(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02},000"


async def create_srt(
    narration_segments: list[dict[str, object]], output_path: Path
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
    cursor = 0
    for index, segment in enumerate(narration_segments, start=1):
        duration = max(3, min(12, len(str(segment.get("text", ""))) // 5))
        blocks.append(
            f"{index}\n{_timestamp(cursor)} --> {_timestamp(cursor + duration)}\n"
            f"{segment.get('text', '')}\n"
        )
        cursor += duration
    output_path.write_text("\n".join(blocks), encoding="utf-8")
    return output_path
