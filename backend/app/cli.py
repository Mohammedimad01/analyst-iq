"""Developer commands. Run from backend/:  python -m app.cli <command>

  migrate         apply database migrations (alembic upgrade head)
  generate        write the synthetic dataset to sample_data/retail_sample.csv
  seed            migrate, generate if missing, and import the synthetic dataset through the normal import pipeline
  gemini-models   list Gemini models your GEMINI_API_KEY can use for text generation (pick one for GEMINI_MODEL)
"""

import argparse
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import BACKEND_DIR, REPO_ROOT, get_settings
from app.demo.synthetic import write_csv

SAMPLE_CSV = REPO_ROOT / "sample_data" / "retail_sample.csv"


def migrate() -> None:
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")


def generate(path: Path = SAMPLE_CSV) -> None:
    count = write_csv(path)
    print(f"Wrote {count:,} synthetic order lines to {path}")


def seed() -> int:
    from app.db.session import SessionLocal
    from app.services.ingestion.importer import run_import
    from app.services.organization import get_demo_org_id

    migrate()
    if not SAMPLE_CSV.exists():
        generate()
    with SessionLocal() as db:
        record = run_import(db, get_demo_org_id(db), SAMPLE_CSV.name, SAMPLE_CSV.read_bytes(),
                            get_settings().max_import_rows)
        print(f"Import #{record.id}: {record.status} - {record.message}")
        return 0 if record.status == "completed" else 1


def gemini_models() -> int:
    from google import genai

    key = get_settings().gemini_api_key
    if not key:
        print("GEMINI_API_KEY is not set in .env")
        return 1
    for model in genai.Client(api_key=key).models.list():
        if "generateContent" in (model.supported_actions or []):
            print(f"{(model.name or '').removeprefix('models/'):45} {model.display_name or ''}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    parser.add_argument("command", choices=("migrate", "generate", "seed", "gemini-models"))
    args = parser.parse_args()
    if args.command == "migrate":
        migrate()
        return 0
    if args.command == "generate":
        generate()
        return 0
    if args.command == "gemini-models":
        return gemini_models()
    return seed()


if __name__ == "__main__":
    sys.exit(main())
