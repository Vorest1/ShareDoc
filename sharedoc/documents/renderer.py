from __future__ import annotations

from pathlib import Path

from docxtpl import DocxTemplate

from ..config import APP
from ..db.repository import ContractBundle
from .context_builder import build_context, build_output_filename
from .templates import TEMPLATE_FILES


class DocumentRenderError(Exception):
    """Ошибка генерации документа."""


def get_template_path(template_key: str) -> Path:
    filename = TEMPLATE_FILES.get(template_key)
    if not filename:
        raise DocumentRenderError(
            "Неизвестный тип шаблона. "
            "Используйте один из: scientific_guidance, qualification, contract_offer"
        )

    path = APP.template_dir / filename
    if not path.exists():
        raise DocumentRenderError(f"Шаблон не найден: {path}")

    return path


def render_document(bundle: ContractBundle, template_key: str) -> Path:
    template_path = get_template_path(template_key)
    context = build_context(bundle, template_key)

    APP.output_dir.mkdir(parents=True, exist_ok=True)
    output_filename = build_output_filename(template_key, bundle.contract)
    output_path = APP.output_dir / output_filename

    try:
        doc = DocxTemplate(template_path)
        doc.render(context)
        doc.save(output_path)
    except Exception as exc:
        raise DocumentRenderError(f"Ошибка генерации документа: {exc}") from exc

    return output_path