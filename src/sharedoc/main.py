from pathlib import Path
from docxtpl import DocxTemplate
from sharedoc.db import get_contract_data


BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "template" / "example.docx"


def generate_contract(contract_id: int, out_dir: Path | None = None) -> Path:
    context = get_contract_data(contract_id)

    print("Template path:", TEMPLATE_PATH)
    print("Exists:", TEMPLATE_PATH.exists())

    doc = DocxTemplate(str(TEMPLATE_PATH))
    doc.render(context)

    out_dir = out_dir or (BASE_DIR.parent.parent / "output")
    out_dir.mkdir(parents=True, exist_ok=True)

    output_path = out_dir / f"contract_{contract_id}.docx"
    doc.save(str(output_path))
    return output_path


def main():
    out = generate_contract(1)
    print(f"Document is created: {out}")
