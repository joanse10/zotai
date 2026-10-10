"""
Punctul de intrare CLI pentru workerul Zotai.

Orchestratorul (sau utilizatorul) invocă workerul ca subproces:
    python -m worker <file.pdf> [opțiuni]

Afișează un singur obiect JSON la stdout. Diagnosticarea se scrie în stderr.

Coduri de ieșire:
    0 — succes
    2 — argumente invalide sau fișier negăsit
    3 — eroare de procesare PDF
"""

import argparse
import json
import sys

from worker.extractor import ExtractConfig, extract_document


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="worker",
        description="Zotai worker: extragere text din PDF (strat de text + OCR)"
    )
    parser.add_argument("pdf", help="Calea către fișierul PDF")
    parser.add_argument("--pages", type=int, default=3,
                        help="Numărul de pagini inițiale de analizat (implicit: 3)")
    parser.add_argument("--threshold", type=int, default=120,
                        help="Prag de caractere pentru a considera documentul scan (implicit: 120)")
    parser.add_argument("--lang", default="ron+rus+eng",
                        help="Limbi Tesseract unite cu '+' (implicit: ron+rus+eng)")
    parser.add_argument("--dpi", type=int, default=300,
                        help="Rezoluția de randare a paginilor pentru OCR (implicit: 300)")
    parser.add_argument("--all", action="store_true", dest="ocr_all",
                        help="OCR pentru întregul document, nu doar primele pagini")
    parser.add_argument("--workers", type=int, default=4,
                        help="Threaduri paralele OCR (implicit: 4)")
    parser.add_argument("--tesseract", default="",
                        help="Cale explicită către tesseract.exe")
    parser.add_argument("--tessdata", default="",
                        help="Director cu fișiere .traineddata (implicit: ./bin/tessdata dacă există)")
    parser.add_argument("--pretty", action="store_true",
                        help="Formatează JSON cu indentare")
    parser.add_argument("--text-out", metavar="FILE",
                        help="Salvează opțional textul extras într-un fișier (UTF-8)")
    args = parser.parse_args()

    cfg = ExtractConfig(
        pages_to_analyze=args.pages,
        scan_char_threshold=args.threshold,
        ocr_languages=args.lang,
        ocr_dpi=args.dpi,
        ocr_all_pages=args.ocr_all,
        ocr_workers=args.workers,
        tesseract_cmd=args.tesseract,
        tessdata_dir=args.tessdata,
    )

    print(f"[worker] Se procesează: {args.pdf}", file=sys.stderr)
    result = extract_document(args.pdf, cfg)

    indent = 2 if args.pretty else None
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=indent))

    if args.text_out and result.text:
        with open(args.text_out, "w", encoding="utf-8") as f:
            f.write(result.text)
        print(f"[worker] Text salvat: {args.text_out}", file=sys.stderr)

    if result.error:
        print(f"[worker] {result.error}", file=sys.stderr)

    if not result.ok:
        return 2 if "nu a fost găsit" in result.error.lower() or "not found" in result.error.lower() else 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
