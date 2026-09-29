import re


SECTION_HEADERS = {
    "education",
    "projects",
    "experience",
    "technical skills",
    "skills",
    "certifications",
    "achievements",
    "summary",
    "professional summary",
    "profile",
}


def clean_resume_text(text: str) -> str:
    text = text.replace("\r", "\n")

    # Join words broken by PDF line wrapping.
    text = re.sub(r"-\s*\n\s*", "", text)

    # Normalize spaces.
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def chunk_resume_text(text: str) -> list[str]:
    text = clean_resume_text(text)

    if not text:
        return []

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    chunks = []
    current_lines = []

    for line in lines:
        normalized = line.lower().strip()

        # Detect major resume section headers.
        if normalized in SECTION_HEADERS:
            if current_lines:
                chunks.append("\n".join(current_lines))
                current_lines = []

            current_lines.append(line)
            continue

        current_lines.append(line)

    if current_lines:
        chunks.append("\n".join(current_lines))

    # Split very large sections into smaller chunks.
    final_chunks = []

    for chunk in chunks:
        if len(chunk) <= 1200:
            final_chunks.append(chunk)
            continue

        paragraphs = re.split(r"\n(?=•|-)", chunk)

        current = ""

        for paragraph in paragraphs:
            paragraph = paragraph.strip()

            if not paragraph:
                continue

            if len(current) + len(paragraph) + 1 <= 1200:
                current = f"{current}\n{paragraph}".strip()
            else:
                if current:
                    final_chunks.append(current)

                current = paragraph

        if current:
            final_chunks.append(current)

    return final_chunks