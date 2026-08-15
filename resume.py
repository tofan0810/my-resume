#!/usr/bin/env python3
import argparse
import itertools
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile

import markdown

preamble = """\
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title} - Resume</title>
<style>
{css}
</style>
</head>
<body>
<div id="resume">
<div id="header">
  <div id="header-text">
    <h1>{title}</h1>
    {contact_lines}
  </div>
  {avatar}
</div>
"""

postamble = """\
</div>
</body>
</html>
"""

CHROME_GUESSES_MACOS = (
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)

# https://stackoverflow.com/a/40674915/409879
CHROME_GUESSES_WINDOWS = (
    # Windows 10
    os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    # Windows 7
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    # Vista
    r"C:\Users\UserName\AppDataLocal\Google\Chrome",
    # XP
    r"C:\Documents and Settings\UserName\Local Settings\Application Data\Google\Chrome",
)

# https://unix.stackexchange.com/a/439956/20079
CHROME_GUESSES_LINUX = [
    "/".join((path, executable))
    for path, executable in itertools.product(
        (
            "/usr/local/sbin",
            "/usr/local/bin",
            "/usr/sbin",
            "/usr/bin",
            "/sbin",
            "/bin",
            "/opt/google/chrome",
        ),
        ("google-chrome", "chrome", "chromium", "chromium-browser"),
    )
]


def guess_chrome_path() -> str:
    if sys.platform == "darwin":
        guesses = CHROME_GUESSES_MACOS
    elif sys.platform == "win32":
        guesses = CHROME_GUESSES_WINDOWS
    else:
        guesses = CHROME_GUESSES_LINUX
    for guess in guesses:
        if os.path.exists(guess):
            logging.info("Found Chrome or Chromium at " + guess)
            return guess
    raise ValueError("Could not find Chrome. Please set CHROME_PATH.")


def title(md: str) -> str:
    """
    Return the contents of the first markdown heading in md, which we
    assume to be the title of the document.
    """
    for line in md.splitlines():
        if re.match("^#[^#]", line):  # starts with exactly one '#'
            return line.lstrip("#").strip()
    raise ValueError(
        "Cannot find any lines that look like markdown h1 headings to use as the title"
    )


def avatar(prefix: str = "resume") -> str:
    """
    Return an <img> tag referencing the avatar photo (prefix.jpg or
    avatar.jpg), or an empty string if no avatar is found.
    """
    candidates = [prefix + ".jpg", "avatar.jpg"]
    for name in candidates:
        if os.path.exists(name):
            return f'<img id="avatar" src="{name}" alt="">'
    return ""


def extract_contact_lines(md: str) -> tuple[str, str]:
    """
    Extract all bullet items between h1 and the first h2, build two
    <p class="contact-line"> rows, and return them together with a
    cleaned version of md that has the h1 + those bullets removed.
    """
    lines = md.splitlines()
    sep = '<span class="sep">|</span>'

    # Find h1 and first h2
    h1_idx = next((i for i, l in enumerate(lines) if re.match(r"^#[^#]", l)), None)
    h2_idx = next((i for i, l in enumerate(lines) if re.match(r"^##", l)), len(lines))

    if h1_idx is None:
        return "", md

    def process_item(s: str) -> str:
        # [text](url) → <a href="url">text</a>
        s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', s)
        # <email@address> → email@address
        s = re.sub(r'<([^>]+@[^>]+)>', r'\1', s)
        return s

    # Collect all bullet lines strictly between h1 and first h2
    all_bullets = []
    bullet_indices = set()
    for i in range(h1_idx + 1, h2_idx):
        stripped = lines[i].strip()
        if stripped.startswith("- "):
            all_bullets.append(process_item(stripped[2:]))
            bullet_indices.add(i)

    # Build two contact rows: first 3 items | remaining items
    rows = []
    if all_bullets[:3]:
        rows.append(
            f'<p class="contact-line">{(" " + sep + " ").join(all_bullets[:3])}</p>'
        )
    if all_bullets[3:]:
        rows.append(
            f'<p class="contact-line">{(" " + sep + " ").join(all_bullets[3:])}</p>'
        )
    contact_html = "\n    ".join(rows)

    # Build cleaned md: drop h1 line + all bullet lines before first h2
    drop = bullet_indices | {h1_idx}
    cleaned_md = "\n".join(l for i, l in enumerate(lines) if i not in drop)
    return contact_html, cleaned_md



def make_html(md: str, prefix: str = "resume", minify=True) -> str:
    """
    Compile md to HTML and prepend/append preamble/postamble.

    Insert <prefix>.css if it exists.
    """
    try:
        with open(prefix + ".css") as cssfp:
            css = cssfp.read()
    except FileNotFoundError:
        print(prefix + ".css not found. Output will by unstyled.")
        css = ""

    doc_title = title(md)
    contact_html, body_md = extract_contact_lines(md)
    av = avatar(prefix)

    html = "".join(
        (
            preamble.format(
                title=doc_title,
                css=css,
                contact_lines=contact_html,
                avatar=av,
            ),
            markdown.markdown(body_md, extensions=["smarty", "abbr"]),
            postamble,
        )
    )
    if minify:
        import minify_html
        html = minify_html.minify(html, remove_processing_instructions=True, minify_css=True)
    return html



def write_pdf(html: str, prefix: str = "resume", chrome: str = "") -> None:
    """
    Write html to prefix.pdf
    """
    chrome = chrome or guess_chrome_path()
    options = [
        "--no-sandbox",
        "--headless",
        "--no-pdf-header-footer",
        "--enable-logging=stderr",
        "--virtual-time-budget=10000",
        "--font-render-hinting=none",
        "--log-level=2",
        "--in-process-gpu",
        "--disable-gpu",
    ]

    # Ideally we'd use tempfile.TemporaryDirectory here. We can't because
    # attempts to delete the tmpdir fail on Windows because Chrome creates a
    # file the python process does not have permission to delete. See
    # https://github.com/puppeteer/puppeteer/issues/2778,
    # https://github.com/puppeteer/puppeteer/issues/298, and
    # https://bugs.python.org/issue26660. If we ever drop Python 3.9 support we
    # can use TemporaryDirectory with ignore_cleanup_errors=True as a context
    # manager.
    tmpdir = tempfile.mkdtemp(prefix="resume.md_")
    options.append(f"--crash-dumps-dir={tmpdir}")
    options.append(f"--user-data-dir={tmpdir}")

    # Write HTML to the same directory so that relative references (e.g. the
    # avatar image) resolve when Chrome renders the PDF.
    html_path = os.path.join(tmpdir, prefix + ".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    # Copy files referenced by <img> tags alongside the HTML
    for match in re.finditer(r'<img[^>]*src="([^"]+)"', html):
        src = match.group(1)
        if not src.startswith(("data:", "http://", "https://")) and os.path.exists(src):
            shutil.copy(src, os.path.join(tmpdir, os.path.basename(src)))

    try:
        subprocess.run(
            [
                chrome,
                *options,
                f"--print-to-pdf={prefix}.pdf",
                "file:///" + html_path.replace("\\", "/"),
            ],
            check=True,
        )
        logging.info(f"Wrote {prefix}.pdf")
    except subprocess.CalledProcessError as exc:
        if exc.returncode == -6:
            logging.warning(
                "Chrome died with <Signals.SIGABRT: 6> "
                f"but you may find {prefix}.pdf was created successfully."
            )
        else:
            raise exc
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if os.path.isdir(tmpdir):
            logging.debug(f"Could not delete {tmpdir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "file",
        help="markdown input file [resume.md]",
        default="resume.md",
        nargs="?",
    )
    parser.add_argument(
        "--no-html",
        help="Do not write html output",
        action="store_true",
    )
    parser.add_argument(
        "--no-pdf",
        help="Do not write pdf output",
        action="store_true",
    )
    parser.add_argument(
        "--chrome-path",
        help="Path to Chrome or Chromium executable",
    )
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.quiet:
        logging.basicConfig(level=logging.WARN, format="%(message)s")
    elif args.debug:
        logging.basicConfig(level=logging.DEBUG, format="%(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    prefix, _ = os.path.splitext(os.path.abspath(args.file))

    with open(args.file, encoding="utf-8") as mdfp:
        md = mdfp.read()
    html = make_html(md, prefix=prefix)

    if not args.no_html:
        with open(prefix + ".html", "w", encoding="utf-8") as htmlfp:
            htmlfp.write(html)
            logging.info(f"Wrote {htmlfp.name}")

    if not args.no_pdf:
        write_pdf(html, prefix=prefix, chrome=args.chrome_path)
