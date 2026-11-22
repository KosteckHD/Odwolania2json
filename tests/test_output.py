import json
import os
import stat

import pytest

from kio_extract.output import write_result


def test_write_result_writes_json_and_negative(tmp_path):
    write_result(tmp_path / "a" / "x.json", {"pole": "wartość"}, "empty_object")
    write_result(tmp_path / "a" / "neg.json", None, "empty_object")
    assert json.loads((tmp_path / "a" / "x.json").read_text(encoding="utf-8")) == {"pole": "wartość"}
    assert (tmp_path / "a" / "neg.json").read_text(encoding="utf-8") == "{}\n"
    assert sorted(p.name for p in (tmp_path / "a").iterdir()) == ["neg.json", "x.json"]


@pytest.mark.skipif(os.name == "nt", reason="uprawnienia POSIX")
def test_write_result_is_readable_by_others(tmp_path):
    path = tmp_path / "x.json"
    write_result(path, {"a": 1}, "empty_object")
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode & stat.S_IRGRP and mode & stat.S_IROTH
