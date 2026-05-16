"""Convert downloaded chapter images to CBZ or PDF outputs."""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bilimanga_dl.core.errors import ConversionError

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = frozenset({"avif", "bmp", "gif", "jpg", "jpeg", "png", "webp"})
PDF_DPI = 100.0
PDF_BATCH_SIZE = 20


def collect_images(directory: Path) -> list[Path]:
    """Return sorted image files in *directory*."""
    return [
        item
        for item in sorted(directory.iterdir())
        if item.is_file() and item.suffix.lstrip(".").lower() in SUPPORTED_IMAGE_EXTENSIONS
    ]


def to_cbz(image_dir: Path, output_path: Path | None = None) -> Path:
    """Create a CBZ archive from a complete chapter image directory."""
    _ensure_convertible(image_dir)
    images = collect_images(image_dir)
    if not images:
        raise ConversionError(f"No images found in {image_dir}")

    output = output_path or (image_dir.parent / f"{image_dir.name}.cbz")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for image in images:
            archive.write(image, image.name)
    return output


def to_collection_cbz(chapters: list[tuple[str, Path]], output_path: Path) -> Path:
    """Create one CBZ from multiple complete chapter directories."""
    if not chapters:
        raise ConversionError("No chapters found for collection archive")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wrote_image = False
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for label, chapter_dir in chapters:
            _ensure_convertible(chapter_dir)
            images = collect_images(chapter_dir)
            if not images:
                raise ConversionError(f"No images found in {chapter_dir}")
            safe_label = _safe_archive_segment(label)
            for image in images:
                archive.write(image, f"{safe_label}/{image.name}")
                wrote_image = True
    if not wrote_image:
        raise ConversionError(f"No images found for {output_path}")
    return output_path


def to_pdf(image_dir: Path, output_path: Path | None = None) -> Path:
    """Create a PDF from a complete chapter image directory."""
    _ensure_convertible(image_dir)
    images = collect_images(image_dir)
    if not images:
        raise ConversionError(f"No images found in {image_dir}")

    output = output_path or (image_dir.parent / f"{image_dir.name}.pdf")
    output.parent.mkdir(parents=True, exist_ok=True)
    _build_pdf_batched(images, output, PDF_DPI, batch_size=max(1, PDF_BATCH_SIZE))
    return output


def convert(image_dir: Path, fmt: str = "cbz", *, optimize: bool = False) -> Path:
    """Convert images using ``cbz``, ``pdf``, or ``both`` format."""
    normalized = fmt.lower().strip()
    if optimize:
        optimize_images(image_dir)

    if normalized == "both":
        to_cbz(image_dir)
        return to_pdf(image_dir)
    if normalized == "pdf":
        return to_pdf(image_dir)
    if normalized == "cbz":
        return to_cbz(image_dir)
    raise ConversionError(f"Unsupported conversion format: {fmt}")


async def convert_async(image_dir: Path, fmt: str = "cbz", *, optimize: bool = False) -> Path:
    """Run conversion in a worker thread."""
    return await asyncio.to_thread(convert, image_dir, fmt, optimize=optimize)


@dataclass(frozen=True)
class OptimizeResult:
    """Result of image optimization."""

    original_bytes: int
    optimized_bytes: int
    converted_count: int
    skipped_count: int

    @property
    def saved_bytes(self) -> int:
        return self.original_bytes - self.optimized_bytes

    @property
    def savings_pct(self) -> float:
        if self.original_bytes == 0:
            return 0.0
        return (self.saved_bytes / self.original_bytes) * 100


def optimize_images(image_dir: Path, *, quality: int = 85) -> OptimizeResult:
    """Convert supported non-WebP images to WebP in place."""
    from PIL import Image

    images = collect_images(image_dir)
    original_bytes = 0
    optimized_bytes = 0
    converted = 0
    skipped = 0

    for image_path in images:
        original_bytes += image_path.stat().st_size
        if image_path.suffix.lower() == ".webp":
            optimized_bytes += image_path.stat().st_size
            skipped += 1
            continue

        try:
            with Image.open(image_path) as source_image:
                image = source_image.convert("RGB") if source_image.mode in {"RGBA", "P", "LA"} else source_image
                webp_path = image_path.with_suffix(".webp")
                image.save(webp_path, "WEBP", quality=quality)
            optimized_bytes += webp_path.stat().st_size
            if image_path != webp_path:
                image_path.unlink()
            converted += 1
        except Exception as exc:
            logger.warning("Skipping image optimization for %s: %s", image_path.name, exc)
            optimized_bytes += image_path.stat().st_size
            skipped += 1

    return OptimizeResult(
        original_bytes=original_bytes,
        optimized_bytes=optimized_bytes,
        converted_count=converted,
        skipped_count=skipped,
    )


def _ensure_convertible(image_dir: Path) -> None:
    if (image_dir / "chapter.state.json").exists():
        raise ConversionError(f"Refusing to convert partial chapter: {image_dir}")
    if not (image_dir / ".complete").exists():
        raise ConversionError(f"Refusing to convert incomplete chapter: {image_dir}")


def _safe_archive_segment(value: str) -> str:
    cleaned = value.replace("\\", " ").replace("/", " ")
    return " ".join(cleaned.split()) or "chapter"


def _build_pdf_batched(image_paths: list[Path], output: Path, dpi: float, *, batch_size: int) -> None:
    from PIL import Image

    def load_batch(paths: list[Path]) -> list[Any]:
        loaded: list[Any] = []
        for path in paths:
            try:
                source_image = Image.open(path)
                image = source_image.convert("RGB") if source_image.mode in {"RGBA", "P", "LA"} else source_image
                loaded.append(image.copy())
                source_image.close()
            except Exception as exc:
                logger.warning("Skipping invalid image %s: %s", path.name, exc)
        return loaded

    if len(image_paths) <= batch_size:
        images = load_batch(image_paths)
        if not images:
            raise ConversionError("No valid images to create PDF")
        _save_images_to_pdf(images, output, dpi)
        return

    with tempfile.TemporaryDirectory(prefix="bilimanga-dl-pdf-") as temp_dir:
        temp_root = Path(temp_dir)
        temp_pdfs: list[Path] = []
        for index in range(0, len(image_paths), batch_size):
            batch_images = load_batch(image_paths[index : index + batch_size])
            if not batch_images:
                continue
            temp_pdf = temp_root / f"batch-{(index // batch_size) + 1:04d}.pdf"
            _save_images_to_pdf(batch_images, temp_pdf, dpi)
            temp_pdfs.append(temp_pdf)
        if not temp_pdfs:
            raise ConversionError("No valid images to create PDF")
        _merge_pdfs(temp_pdfs, output)


def _save_images_to_pdf(images: list[Any], output: Path, dpi: float) -> None:
    first, *rest = images
    try:
        first.save(output, "PDF", resolution=dpi, save_all=True, append_images=rest)
    finally:
        for image in images:
            image.close()


def _merge_pdfs(pdf_paths: list[Path], output: Path) -> None:
    if len(pdf_paths) == 1:
        shutil.copy2(pdf_paths[0], output)
        return
    try:
        from pypdf import PdfWriter
    except ImportError as exc:
        raise ConversionError(
            "Large PDF conversion requires `pypdf`. Install it and retry; "
            "refusing to create an incomplete PDF."
        ) from exc

    writer = PdfWriter()
    try:
        for path in pdf_paths:
            writer.append(str(path))
        writer.write(str(output))
    finally:
        writer.close()
