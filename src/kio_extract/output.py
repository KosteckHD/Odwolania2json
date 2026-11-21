import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from .contracts import JsonObject


def write_result(path: Path, data: JsonObject | None, negative_mode: str) -> None:
    if data is None:
        content = "" if negative_mode == "empty_file" else "{}\n"
    else:
        content = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"

    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content.encode("utf-8"))
            stream.close()
            temporary.replace(path)
        finally:
            stream.close()
            temporary.unlink(missing_ok=True)
