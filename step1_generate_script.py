"""Step 1 - read a PDF/TXT from inputs/documents and ask Claude for a 60-second voice-over script.

Run on its own:   python step1_generate_script.py
Result:           output/<document name>_script.txt
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from config import (
    DOCUMENTS_DIR,
    OUTPUT_DIR,
    ReelsError,
    check_python,
    ensure_folders,
    env_flag,
    load_env,
    newest_first,
    setup_console,
    show,
)

# The instruction sent to Claude, exactly as specified for this project.
PROMPT = (
    "Sen uzman bir tarih belgeseli yapımcısı ve Instagram Reels içerik üreticisisin. "
    "Sana verilen bu akademik makaleyi/metni oku. En çarpıcı, ilginç ve dramatik "
    "kısımlarını seçerek tam 60 saniyelik bir seslendirme metni (yaklaşık 120-140 kelime) "
    "hazırla. İzleyiciyi ekranda tutacak kancalarla (hook) dolu olmalı. "
    "Sadece okunacak metni ver."
)

DEFAULT_MODEL = "claude-opus-5-5"
# Thinking tokens count towards max_tokens, so leave plenty of room for a ~140-word answer.
MAX_TOKENS = 16000
SUPPORTED_EXTENSIONS = {".pdf", ".txt"}
# Opt-in beta that lets the API retry a (rare, usually false-positive) safety refusal on another model.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


# --------------------------------------------------------------------------- reading input
def find_document(explicit: Path | None = None) -> Path:
    """Return the file to process: the one given with --input, else the newest in inputs/documents."""
    if explicit is not None:
        path = explicit if explicit.is_absolute() else Path.cwd() / explicit
        if not path.is_file():
            raise ReelsError(f"The file '{explicit}' does not exist.")
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ReelsError(f"'{path.name}' is not a .pdf or .txt file.")
        return path

    candidates = [
        p
        for p in DOCUMENTS_DIR.iterdir()
        if p.is_file()
        and p.suffix.lower() in SUPPORTED_EXTENSIONS
        and not p.name.startswith(("~", "."))
    ]
    if not candidates:
        raise ReelsError(
            f"No PDF or TXT file found in '{show(DOCUMENTS_DIR)}'. "
            "Copy your article there and run the program again."
        )
    candidates = newest_first(candidates)
    if len(candidates) > 1:
        names = ", ".join(p.name for p in candidates)
        print(f"  Several documents found ({names}).")
        print(f"  Using the most recently modified one: {candidates[0].name}")
        print("  (Use --input to choose a different file.)")
    return candidates[0]


def read_pdf(path: Path) -> str:
    from PyPDF2 import PdfReader
    from PyPDF2.errors import PyPdfError

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ReelsError(f"'{path.name}' is password-protected. Remove the password and try again.")
        pages = []
        for page in reader.pages:
            try:
                pages.append((page.extract_text() or "").strip())
            except Exception:  # one unreadable page should not stop the whole document
                pages.append("")
    except PyPdfError as exc:
        raise ReelsError(f"Could not read '{path.name}' as a PDF: {exc}") from exc
    return "\n\n".join(p for p in pages if p)


def read_txt(path: Path) -> str:
    raw = path.read_bytes()
    # utf-8 first, then the encodings older Turkish Windows programs use.
    for encoding in ("utf-8-sig", "cp1254", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def read_document(path: Path) -> str:
    text = read_pdf(path) if path.suffix.lower() == ".pdf" else read_txt(path)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        hint = (
            " It is probably a scanned PDF (pictures of pages). Run OCR on it first, "
            "or save the text as a .txt file."
            if path.suffix.lower() == ".pdf"
            else ""
        )
        raise ReelsError(f"No text could be extracted from '{path.name}'.{hint}")
    return text


# --------------------------------------------------------------------------- talking to Claude
def explain_api_error(exc: Exception) -> ReelsError:
    import anthropic

    if isinstance(exc, anthropic.AuthenticationError):
        return ReelsError(
            "Anthropic rejected the API key. Open the .env file and check that ANTHROPIC_API_KEY "
            "is copied completely, without spaces or quotes."
        )
    if isinstance(exc, anthropic.PermissionDeniedError):
        return ReelsError(f"This API key is not allowed to use that model: {exc.message}")
    if isinstance(exc, anthropic.NotFoundError):
        return ReelsError(
            "Anthropic does not know that model name. Remove CLAUDE_MODEL from the .env file "
            f"to use the default ({DEFAULT_MODEL})."
        )
    if isinstance(exc, anthropic.RateLimitError):
        return ReelsError("Anthropic says there were too many requests. Wait a minute and try again.")
    if isinstance(exc, anthropic.BadRequestError):
        return ReelsError(
            f"Anthropic could not process the request: {exc.message}\n"
            "  If this mentions credits or billing, add credit at https://console.anthropic.com "
            "(Plans & Billing). If the document is extremely long, try a shorter excerpt."
        )
    if isinstance(exc, anthropic.APIConnectionError):
        return ReelsError("Could not reach Anthropic. Check your internet connection and try again.")
    if isinstance(exc, anthropic.APIStatusError):
        return ReelsError(f"Anthropic returned an error ({exc.status_code}): {exc.message}")
    return ReelsError(str(exc))


def ask_claude(document_text: str, model: str) -> str:
    import anthropic

    api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not api_key or api_key.lower().startswith("your"):
        raise ReelsError(
            "No API key found. Create a file named '.env' next to main.py containing the line:\n"
            "  ANTHROPIC_API_KEY=sk-ant-...\n"
            "See the README, section 'Set up the .env file'."
        )

    client = anthropic.Anthropic(api_key=api_key)
    request = dict(
        model=model,
        max_tokens=MAX_TOKENS,
        system=PROMPT,
        messages=[{"role": "user", "content": document_text}],
    )

    use_fallbacks = env_flag("CLAUDE_FALLBACKS", default=True)
    try:
        if use_fallbacks:
            try:
                response = client.beta.messages.create(
                    betas=[FALLBACK_BETA], fallbacks="default", **request
                )
            except anthropic.BadRequestError as exc:
                # This beta is not available for every model/account; the script works without it.
                print(f"  (Refusal fallback not accepted: {exc.message} - retrying without it.)")
                response = client.messages.create(**request)
        else:
            response = client.messages.create(**request)
    except anthropic.APIError as exc:
        raise explain_api_error(exc) from exc

    if response.stop_reason == "refusal":
        raise ReelsError(
            "Claude declined to write a script for this document. Try a different text or excerpt."
        )
    if response.stop_reason == "max_tokens":
        raise ReelsError("Claude's answer was cut off before it finished. Please run the program again.")

    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise ReelsError("Claude returned an empty answer. Please run the program again.")
    return text


# --------------------------------------------------------------------------- cleaning the answer
def clean_script(text: str) -> str:
    """Strip markdown and stage directions so only words meant to be spoken remain."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"\[[^\]]*\]", " ", text)  # [Müzik], [1] ...
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)  # headings
    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.MULTILINE)  # bullets
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)  # quotes
    text = re.sub(r"[*_`]{1,3}", "", text)  # bold / italic / code marks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > 1 and text[0] in "\"“" and text[-1] in "\"”":
        text = text[1:-1].strip()
    return text


# --------------------------------------------------------------------------- public entry point
def generate_script(input_path: Path | None = None, model: str | None = None) -> Path:
    """Run step 1 and return the path of the saved script."""
    ensure_folders()
    load_env()
    model = model or os.getenv("CLAUDE_MODEL", "").strip() or DEFAULT_MODEL

    document = find_document(input_path)
    print(f"  Reading: {show(document)}")
    text = read_document(document)
    print(f"  {len(text):,} characters read.")

    print(f"  Asking Claude ({model}) to write the script - this takes about 10-30 seconds...")
    script = clean_script(ask_claude(text, model))

    words = len(script.split())
    print(f"  Script ready: {words} words.")
    if not 100 <= words <= 160:
        print("  Note: the target is roughly 120-140 words, so the video may be shorter or longer than 60 seconds.")

    out_path = OUTPUT_DIR / f"{document.stem}_script.txt"
    out_path.write_text(script + "\n", encoding="utf-8")
    print(f"  Saved: {show(out_path)}")
    return out_path


def build_arg_parser(add_help: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=add_help)
    parser.add_argument(
        "--input", type=Path, help="PDF or TXT file to use (default: newest file in inputs/documents)"
    )
    parser.add_argument(
        "--model", help=f"Claude model to use (default: {DEFAULT_MODEL}, or CLAUDE_MODEL from .env)"
    )
    return parser


def main() -> None:
    setup_console()
    args = build_arg_parser().parse_args()
    try:
        check_python()
        generate_script(args.input, args.model)
    except ReelsError as exc:
        raise SystemExit(f"\nERROR: {exc}")


if __name__ == "__main__":
    main()
