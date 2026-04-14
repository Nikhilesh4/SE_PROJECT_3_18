import fitz

from app.services.errors import InvalidPDFError


class PDFExtractor:
    def extract(self, pdf_bytes: bytes) -> str:
        try:
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                text = "\n".join(page.get_text() for page in doc)
        except Exception as exc:
            raise InvalidPDFError("Unable to read PDF file") from exc

        cleaned = text.strip()
        if not cleaned:
            raise InvalidPDFError("Uploaded PDF appears to be empty")

        return cleaned
