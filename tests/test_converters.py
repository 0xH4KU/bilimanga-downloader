from __future__ import annotations

import builtins
import zipfile
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from bilimanga_dl.core.converters import (
    OptimizeResult,
    collect_images,
    convert,
    optimize_images,
    to_cbz,
    to_pdf,
)
from bilimanga_dl.core.errors import ConversionError

if TYPE_CHECKING:
    from pathlib import Path

_ORIGINAL_IMPORT = builtins.__import__


def _block_pdf_merge_backends(name: str, *args: object, **kwargs: object):
    if name == "pypdf":
        raise ImportError(f"blocked import for test: {name}")
    return _ORIGINAL_IMPORT(name, *args, **kwargs)


def _create_test_images(directory: Path, count: int = 3, fmt: str = "png") -> list[Path]:
    from PIL import Image

    files: list[Path] = []
    for index in range(1, count + 1):
        path = directory / f"{index:03d}.{fmt}"
        image = Image.new("RGB", (10, 10), color=(index * 30, index * 20, index * 10))
        image.save(path, fmt.upper() if fmt != "jpg" else "JPEG")
        image.close()
        files.append(path)
    return files


def test_collect_images_sorts_supported_formats_and_ignores_markers(tmp_path: Path) -> None:
    (tmp_path / "003.JPG").write_bytes(b"x")
    (tmp_path / "001.png").write_bytes(b"x")
    (tmp_path / ".complete").touch()
    (tmp_path / "notes.txt").write_text("nope", encoding="utf-8")
    (tmp_path / "002.webp").write_bytes(b"x")

    assert [item.name for item in collect_images(tmp_path)] == ["001.png", "002.webp", "003.JPG"]


def test_to_cbz_requires_complete_chapter_and_creates_archive(tmp_path: Path) -> None:
    image_dir = tmp_path / "Chapter"
    image_dir.mkdir()
    _create_test_images(image_dir, count=2)
    (image_dir / ".complete").touch()

    result = to_cbz(image_dir)

    assert result == tmp_path / "Chapter.cbz"
    with zipfile.ZipFile(result) as archive:
        assert archive.namelist() == ["001.png", "002.png"]


def test_conversion_refuses_partial_chapter(tmp_path: Path) -> None:
    image_dir = tmp_path / "Chapter"
    image_dir.mkdir()
    _create_test_images(image_dir, count=1)
    (image_dir / "chapter.state.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ConversionError, match="partial"):
        convert(image_dir, "cbz")


def test_to_pdf_creates_valid_pdf(tmp_path: Path) -> None:
    image_dir = tmp_path / "Chapter"
    image_dir.mkdir()
    _create_test_images(image_dir, count=2)
    (image_dir / ".complete").touch()

    result = to_pdf(image_dir)

    assert result == tmp_path / "Chapter.pdf"
    assert result.read_bytes().startswith(b"%PDF")


def test_both_format_creates_cbz_and_pdf(tmp_path: Path) -> None:
    image_dir = tmp_path / "Chapter"
    image_dir.mkdir()
    _create_test_images(image_dir, count=1)
    (image_dir / ".complete").touch()

    result = convert(image_dir, "both")

    assert result == tmp_path / "Chapter.pdf"
    assert (tmp_path / "Chapter.cbz").exists()
    assert (tmp_path / "Chapter.pdf").exists()


def test_empty_directory_raises_conversion_error(tmp_path: Path) -> None:
    image_dir = tmp_path / "Empty"
    image_dir.mkdir()
    (image_dir / ".complete").touch()

    with pytest.raises(ConversionError, match="No images found"):
        to_cbz(image_dir)


def test_bad_images_raise_conversion_error_for_pdf(tmp_path: Path) -> None:
    image_dir = tmp_path / "Bad"
    image_dir.mkdir()
    (image_dir / ".complete").touch()
    (image_dir / "001.jpg").write_bytes(b"not an image")

    with pytest.raises(ConversionError, match="No valid images"):
        to_pdf(image_dir)


def test_large_pdf_requires_pypdf_merge_backend(tmp_path: Path) -> None:
    image_dir = tmp_path / "Large"
    image_dir.mkdir()
    _create_test_images(image_dir, count=5)
    (image_dir / ".complete").touch()

    with (
        patch("bilimanga_dl.core.converters.PDF_BATCH_SIZE", 2),
        patch("builtins.__import__", side_effect=_block_pdf_merge_backends),
        pytest.raises(ConversionError, match="Large PDF conversion requires"),
    ):
        to_pdf(image_dir)


def test_large_pdf_merges_all_pages_with_pypdf(tmp_path: Path) -> None:
    from pypdf import PdfReader

    image_dir = tmp_path / "Large"
    image_dir.mkdir()
    _create_test_images(image_dir, count=5)
    (image_dir / ".complete").touch()

    with patch("bilimanga_dl.core.converters.PDF_BATCH_SIZE", 2):
        result = to_pdf(image_dir)

    assert len(PdfReader(str(result)).pages) == 5


def test_optimize_images_converts_png_to_webp(tmp_path: Path) -> None:
    image_dir = tmp_path / "Chapter"
    image_dir.mkdir()
    _create_test_images(image_dir, count=1, fmt="png")

    result = optimize_images(image_dir, quality=80)

    assert isinstance(result, OptimizeResult)
    assert result.converted_count == 1
    assert result.skipped_count == 0
    assert not (image_dir / "001.png").exists()
    assert (image_dir / "001.webp").exists()


def test_convert_optimize_flag_runs_optimizer_before_archive(tmp_path: Path) -> None:
    image_dir = tmp_path / "Chapter"
    image_dir.mkdir()
    _create_test_images(image_dir, count=1, fmt="png")
    (image_dir / ".complete").touch()

    result = convert(image_dir, "cbz", optimize=True)

    assert result.suffix == ".cbz"
    assert (image_dir / "001.webp").exists()
