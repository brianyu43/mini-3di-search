import io
import tarfile
from dataclasses import replace

import pytest

from mini3di_search.prepare import DownloadSpec, download, dry_run, safe_extract


def spec(size=3):
    return DownloadSpec(
        "tiny", "https://example.org/tiny", size, "v1", "test", "fixture", "fixture"
    )


def test_budgets_unknown_and_total():
    assert dry_run([spec()])["all_allowed"]
    for value in (None, 306064157):
        assert not dry_run([spec(value)])["all_allowed"]
    assert dry_run([spec(306064157)], max_file_bytes=300 * 1024**2)["all_allowed"]
    assert not dry_run([replace(spec(250 * 1024**2), name=str(i)) for i in range(5)])["all_allowed"]


def test_download_size_bounds_and_no_overwrite(tmp_path, monkeypatch):
    class Response(io.BytesIO):
        status = 200
        url = "https://example.org/tiny"
        headers = {}

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: Response(b"abc"))
    result = download(spec(), tmp_path)
    assert result["bytes"] == 3 and (tmp_path / "tiny").read_bytes() == b"abc"
    with pytest.raises(FileExistsError):
        download(spec(), tmp_path)
    for body in (b"a", b"abcd"):
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, body=body, **kw: Response(body))
        with pytest.raises(ValueError):
            download(replace(spec(), name="bad"), tmp_path)
        assert not (tmp_path / "bad").exists()
        assert not list(tmp_path.glob("*.partial"))


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a/../../escape", "a\\b"])
def test_download_names(name):
    with pytest.raises(ValueError):
        replace(spec(), name=name)


def archive(path, members):
    with tarfile.open(path, "w") as tar:
        for name, kind in members:
            item = tarfile.TarInfo(name)
            item.type = kind
            if kind == tarfile.REGTYPE:
                item.size = 3
                tar.addfile(item, io.BytesIO(b"abc"))
            else:
                item.linkname = "/outside"
                tar.addfile(item)


@pytest.mark.parametrize(
    "members",
    [
        [("../escape", tarfile.REGTYPE)],
        [("/absolute", tarfile.REGTYPE)],
        [("a\\b", tarfile.REGTYPE)],
        [("link", tarfile.SYMTYPE)],
        [("link", tarfile.LNKTYPE)],
        [("device", tarfile.CHRTYPE)],
        [("same", tarfile.REGTYPE), ("same", tarfile.REGTYPE)],
    ],
)
def test_unsafe_archives_write_nothing(tmp_path, members):
    path = tmp_path / "bad.tar"
    archive(path, members)
    with pytest.raises(ValueError):
        safe_extract(path, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_safe_archive_hashes_and_expansion_limit(tmp_path):
    path = tmp_path / "good.tar"
    archive(path, [("nested/file", tarfile.REGTYPE)])
    with pytest.raises(ValueError, match="budget"):
        safe_extract(path, tmp_path / "rejected", max_bytes=2)
    manifest = safe_extract(path, tmp_path / "out")
    assert manifest[0]["bytes"] == 3 and len(manifest[0]["sha256"]) == 64
    assert (tmp_path / "out/nested/file").read_bytes() == b"abc"
    with pytest.raises(FileExistsError):
        safe_extract(path, tmp_path / "out")


def test_selected_extract_checks_unselected_members_and_bounds(tmp_path):
    path = tmp_path / "subset.tar"
    archive(path, [("a", tarfile.REGTYPE), ("b", tarfile.REGTYPE)])
    result = safe_extract(path, tmp_path / "out", selected_names={"a"}, max_bytes=3)
    assert [row["path"] for row in result] == ["a"]
    assert not (tmp_path / "out/b").exists()
    for selected in (set(), {"missing"}):
        with pytest.raises(ValueError, match="empty or missing"):
            safe_extract(path, tmp_path / "absent", selected_names=selected)
    archive(path, [("a", tarfile.REGTYPE), ("../evil", tarfile.REGTYPE)])
    with pytest.raises(ValueError, match="unsafe"):
        safe_extract(path, tmp_path / "unsafe", selected_names={"a"})
