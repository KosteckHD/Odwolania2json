import sys
from pathlib import Path


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from dotenv import load_dotenv
    from kio_extract.cli import main

    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
    raise SystemExit(main())
