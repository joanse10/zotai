"""
Adaptor AI pentru extragerea metadatelor bibliografice (TZ.md §5).

Pipeline: eșantion de text din document -> prompt -> agent CLI (agy / claude /
comandă personalizată) -> analiză JSON -> câmpuri BookMetadata.

Șablonul de comandă (setarea cli_template) suportă substituenți:
  {prompt} — promptul transmis ca argument în linia de comandă
  {file}   — promptul scris într-un fișier temporar, calea este substituită
  (fără substituenți, promptul este transmis prin stdin al procesului)

Limita Windows pentru lungimea argumentelor (~32k) este ocolită prin
trunchierea eșantionului de text.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

# Ne asigurăm că rădăcina proiectului este în path la invocarea directă
_WORKSPACE_ROOT = str(Path(__file__).resolve().parent.parent)
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

from zotero.item_types import AI_OUTPUT_SCHEMA, type_label

# Coduri de escape ANSI emise de agenții CLI
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def resolve_cli_binary(cmd: str) -> str:
    """
    Găsește fișierul executabil real pentru agentul CLI (în special pe Windows).
    Detectează automat Antigravity CLI (agy), Claude Code etc.
    """
    if not cmd:
        cmd = "agy"
    cmd_clean = cmd.strip().strip('"').strip("'")

    if os.path.isfile(cmd_clean):
        return cmd_clean

    found = shutil.which(cmd_clean)
    if found:
        return found

    # Detectarea automată a Antigravity CLI pe Windows
    if cmd_clean.lower() in ("agy", "agy.exe"):
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\agy\bin\agy.exe"),
            os.path.expandvars(r"%USERPROFILE%\AppData\Local\agy\bin\agy.exe"),
            os.path.expanduser("~/.local/bin/agy.exe"),
            os.path.expanduser("~/.local/bin/agy"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                bin_dir = os.path.dirname(c)
                if bin_dir not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
                return c

    elif cmd_clean.lower() in ("claude", "claude.cmd", "claude.exe"):
        candidates = [
            os.path.expandvars(r"%APPDATA%\npm\claude.cmd"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Claude\claude.exe"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c

    return cmd_clean


@dataclass
class AIConfig:
    cli_template: str = "agy -p {prompt} --output-format text --effort low --dangerously-skip-permissions"
    timeout: int = 60                # secunde pentru un apel AI
    max_prompt_chars: int = 2500     # limita eșantionului de text (primele pagini conțin info bibliografică)
    enabled: bool = True             # False — se omite etapa AI


# Preseturi de agenți CLI
CLI_PRESET_TEMPLATES = {
    "antigravity": "{cmd} -p {prompt} --output-format text --effort low --dangerously-skip-permissions",
    "agy": "{cmd} -p {prompt} --output-format text --effort low --dangerously-skip-permissions",
    "claude": "{cmd} -p {prompt}",
}


def build_cli_template(preset: str, cmd: str) -> str:
    """Construiește șablonul de invocare din numele presetului și comanda executabilă."""
    cmd = (cmd or "agy").strip()
    if "{prompt}" in cmd or "{file}" in cmd:
        return cmd
    preset_lower = (preset or "").lower()
    for key, tpl in CLI_PRESET_TEMPLATES.items():
        if key in preset_lower:
            return tpl.replace("{cmd}", cmd)
    if "agy" in cmd.lower():
        return CLI_PRESET_TEMPLATES["agy"].replace("{cmd}", cmd)
    return f"{cmd} -p {{prompt}}"


SYSTEM_PROMPT = """Ești un expert în extragerea metadatelor bibliografice. Nu folosi instrumente sau comenzi externe; lucrează strict cu textul documentului furnizat.
Extrage metadatele din paginile de titlu / eșantionul de text și returnează STRICT un singur obiect JSON, fără explicații sau blocuri de cod markdown.

Schema JSON cerută (șir gol sau listă goală pentru câmpurile care nu pot fi determinate):
%s

Reguli:
- item_type trebuie să fie una dintre: book, bookSection, journalArticle, conferencePaper, thesis, report, preprint, manuscript, document, magazineArticle, newspaperArticle, encyclopediaArticle, dictionaryEntry
- authors și editors trebuie să fie tablouri de șiruri „Prenume Nume"
- language trebuie să fie un cod ISO 639-1/3 (ron, eng, rus, fra, deu...)
- confidence: de la 0.0 la 1.0 reprezentând încrederea ta
- Nu afișa NIMIC în afară de JSON valid.""" % json.dumps(AI_OUTPUT_SCHEMA, ensure_ascii=False, indent=2)


def build_prompt(text_sample: str, language_hint: str = "", cfg: Optional[AIConfig] = None) -> str:
    """Construiește promptul pentru agentul AI din textul extras."""
    cfg = cfg or AIConfig()
    sample = text_sample[:cfg.max_prompt_chars]
    hint = f"\nSugestie privind limba documentului: {language_hint}" if language_hint else ""
    return f"{SYSTEM_PROMPT}{hint}\n\nTextul documentului:\n{sample}"


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def parse_ai_json(output: str) -> Optional[Dict]:
    """
    Extrage obiectul JSON din ieșirea CLI: elimină codurile ANSI, testează
    ieșirea completă, apoi blocurile markdown și fragmentele {...} echilibrate.
    """
    text = strip_ansi(output).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    for m in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL):
        try:
            return json.loads(m.group(1))
        except Exception:
            continue

    best = None
    for m in re.finditer(r"\{", text):
        depth, start = 0, m.start()
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    chunk = text[start:i + 1]
                    try:
                        obj = json.loads(chunk)
                        if best is None or len(chunk) > len(json.dumps(best)):
                            best = obj
                    except Exception:
                        pass
                    break
    return best


def run_cli(prompt: str, cfg: AIConfig) -> Tuple[Optional[str], str]:
    """
    Execută apelul CLI. Returnează (stdout, eroare).
    Suportă substituenții {prompt} și {file} în șablonul de comandă.
    """
    tokens = cfg.cli_template.split()
    if not tokens:
        return None, "Șablonul de comandă CLI este gol"

    resolved_bin = resolve_cli_binary(tokens[0])
    tokens[0] = resolved_bin

    tmp_path = None
    stdin_data = None
    try:
        if "{file}" in tokens:
            fd, tmp_path = tempfile.mkstemp(suffix=".txt", prefix="zotai_prompt_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(prompt)
            tokens = [tmp_path if t == "{file}" else t for t in tokens]
        elif "{prompt}" in tokens:
            tokens = [prompt if t == "{prompt}" else t for t in tokens]
        else:
            stdin_data = prompt

        if "agy" in os.path.basename(resolved_bin).lower():
            if "--output-format" not in tokens:
                tokens.extend(["--output-format", "text"])
            if "--effort" not in tokens:
                tokens.extend(["--effort", "low"])
            if "--dangerously-skip-permissions" not in tokens:
                tokens.append("--dangerously-skip-permissions")
            if "--disable-slash-commands" not in tokens:
                tokens.append("--disable-slash-commands")

        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        proc = subprocess.run(
            tokens,
            input=stdin_data,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=cfg.timeout, **kwargs
        )
        if proc.returncode != 0:
            return None, f"CLI s-a terminat cu codul {proc.returncode}: {(proc.stderr or '').strip()[:300]}"
        return proc.stdout, ""
    except FileNotFoundError:
        return None, f"Comanda CLI nu a fost găsită: {tokens[0]}"
    except subprocess.TimeoutExpired:
        return None, f"Timeout CLI ({cfg.timeout}s)"
    except Exception as e:
        return None, f"Eroare la execuția CLI: {e}"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def ai_fields_to_metadata(data: Dict) -> Dict:
    """Convertește dicționarul JSON AI în kwargs pentru BookMetadata."""
    def _join(v):
        return ", ".join(v) if isinstance(v, list) else str(v or "")

    item_type = str(data.get("item_type") or data.get("type") or "book")
    return {
        "doc_type": type_label(item_type),
        "title": str(data.get("title") or ""),
        "subtitle": str(data.get("subtitle") or ""),
        "short_title": str(data.get("short_title") or ""),
        "authors": _join(data.get("authors")),
        "editors": _join(data.get("editors")),
        "publisher": str(data.get("publisher") or ""),
        "year": str(data.get("year") or ""),
        "city": str(data.get("city") or ""),
        "edition": str(data.get("edition") or ""),
        "series": str(data.get("series") or ""),
        "series_number": str(data.get("series_number") or ""),
        "volume": str(data.get("volume") or ""),
        "num_volumes": str(data.get("num_volumes") or ""),
        "num_pages": str(data.get("num_pages") or ""),
        "isbn": str(data.get("isbn") or ""),
        "issn": str(data.get("issn") or ""),
        "doi": str(data.get("doi") or ""),
        "url": str(data.get("url") or ""),
        "language": str(data.get("language") or "").upper(),
        "abstract": str(data.get("abstract") or ""),
        "extra": str(data.get("extra") or ""),
        "confidence": float(data.get("confidence") or 0.5),
        "raw_json": json.dumps(data, ensure_ascii=False, indent=2),
    }


def analyze_text(text_sample: str, cfg: Optional[AIConfig] = None,
                 language_hint: str = "") -> Tuple[Optional[Dict], str]:
    """
    Etapa AI completă: prompt -> CLI -> JSON -> câmpuri BookMetadata.
    Returnează (fields_dict | None, eroare).
    """
    cfg = cfg or AIConfig()
    if not text_sample.strip():
        return None, "Nu există text de analizat (documentul nu conține text)"

    prompt = build_prompt(text_sample, language_hint, cfg)
    output, err = run_cli(prompt, cfg)
    if err:
        return None, err

    data = parse_ai_json(output or "")
    if not data:
        return None, f"Nu s-a putut extrage JSON din ieșirea CLI: {(output or '')[:200]}"
    return ai_fields_to_metadata(data), ""
