import json
import os
import io
import base64
import logging
import re
import traceback

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def compress_image_bytes(img_bytes, quality=0.6, max_dim=1200):
    """Downscale and compress raw image bytes using Pillow (PIL)."""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(img_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        w, h = img.size
        if w > max_dim or h > max_dim:
            if w > h:
                h = int((h * max_dim) / w)
                w = max_dim
            else:
                w = int((w * max_dim) / h)
                h = max_dim
            img = img.resize((w, h), Image.Resampling.LANCZOS)

        output = io.BytesIO()
        qual_int = max(1, min(100, int(quality * 100)))
        img.save(output, format="JPEG", quality=qual_int, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.debug(f"Image compression skipped/failed: {e}")
        return img_bytes


def compress_html_images(html_str, quality=0.6, max_dim=1200):
    """Find and compress inline base64 images in HTML content."""
    pattern = re.compile(r'data:image/([^;]+);base64,([A-Za-z0-9+/=\s]+)')

    def replacer(match):
        b64_data = match.group(2).strip()
        try:
            raw_bytes = base64.b64decode(b64_data)
            compressed = compress_image_bytes(raw_bytes, quality, max_dim)
            new_b64 = base64.b64encode(compressed).decode("utf-8")
            return f"data:image/jpeg;base64,{new_b64}"
        except Exception:
            return match.group(0)

    return pattern.sub(replacer, html_str)


def convert_html_to_pdf(html_content, pdf_format="A4"):
    """Convert HTML string to PDF bytes using available Python engines."""
    errors = []

    # 1. Primary Engine: xhtml2pdf (Pure Python HTML/CSS to PDF)
    try:
        from xhtml2pdf import pisa

        output = io.BytesIO()
        pdf = pisa.pisaDocument(io.BytesIO(html_content.encode("utf-8")), output)
        if not pdf.err:
            return output.getvalue()
        else:
            errors.append(f"xhtml2pdf error count: {pdf.err}")
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"xhtml2pdf import/execution failed: {tb}")
        errors.append(f"xhtml2pdf failed ({type(e).__name__}: {str(e)})")

    # 2. Secondary Engine: WeasyPrint
    try:
        from weasyprint import HTML

        output = io.BytesIO()
        HTML(string=html_content).write_pdf(output)
        return output.getvalue()
    except Exception as e:
        errors.append(f"weasyprint failed ({type(e).__name__}: {str(e)})")

    # 3. Tertiary Engine: pdfkit (wkhtmltopdf)
    try:
        import pdfkit

        config = None
        if os.path.exists("/opt/bin/wkhtmltopdf"):
            config = pdfkit.configuration(wkhtmltopdf="/opt/bin/wkhtmltopdf")
        pdf_bytes = pdfkit.from_string(html_content, False, configuration=config)
        if pdf_bytes:
            return pdf_bytes
    except Exception as e:
        errors.append(f"pdfkit failed ({type(e).__name__}: {str(e)})")

    # 4. Quaternary Engine: Pyppeteer
    try:
        import asyncio
        from pyppeteer import launch

        async def _pyppeteer_pdf():
            executable_path = os.getenv("CHROMIUM_PATH") or os.getenv("CHROME_PATH")
            launch_kwargs = {
                "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
                "headless": True,
            }
            if executable_path and os.path.exists(executable_path):
                launch_kwargs["executablePath"] = executable_path
            browser = await launch(**launch_kwargs)
            try:
                page = await browser.newPage()
                await page.setContent(html_content, waitUntil="networkidle0")
                return await page.pdf({"format": pdf_format, "printBackground": True})
            finally:
                await browser.close()

        return asyncio.run(_pyppeteer_pdf())
    except Exception as e:
        errors.append(f"pyppeteer failed ({type(e).__name__}: {str(e)})")

    error_details = " | ".join(errors)
    raise RuntimeError(
        f"No HTML-to-PDF engine succeeded. Detailed Errors: {error_details}"
    )


def generate_pdf(body):
    html = body.get("html")
    if not html or not isinstance(html, str):
        raise ValueError("html is required")

    image_quality = float(body.get("imageQuality", 0.6))
    max_dimension = int(body.get("maxImageDimension", 1200))
    pdf_format = body.get("format", "A4")

    # Step 1: Compress inline images in HTML
    compressed_html = compress_html_images(html, image_quality, max_dimension)

    # Convert HTML to PDF bytes
    pdf_bytes = convert_html_to_pdf(compressed_html, pdf_format=pdf_format)

    # Step 2: 5.8MB Safety check for AWS Lambda payload limit
    MAX_ALLOWED_BYTES = int(5.8 * 1024 * 1024)
    if len(pdf_bytes) > MAX_ALLOWED_BYTES:
        logger.warning(
            f"PDF size ({len(pdf_bytes) / (1024*1024):.2f} MB) exceeds threshold. Retrying with aggressive image compression..."
        )
        aggressive_html = compress_html_images(html, 0.3, 800)
        pdf_bytes = convert_html_to_pdf(aggressive_html, pdf_format=pdf_format)

    return pdf_bytes


def lambda_handler(event, context=None):
    logger.info(f"============== Event: {event}")

    # Parse body payload (supports direct invocation, API Gateway, Function URL)
    body = {}
    if isinstance(event, dict):
        if "body" in event:
            if isinstance(event["body"], str):
                try:
                    body = json.loads(event["body"])
                except Exception:
                    body = {}
            elif isinstance(event["body"], dict):
                body = event["body"]
        else:
            body = event

    pdf_bytes = generate_pdf(body)

    # Encode PDF bytes to Base64 string
    encoded_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

    # Check if request originated from HTTP API Gateway or Lambda Function URL proxy
    is_http_proxy = isinstance(event, dict) and (
        "requestContext" in event or "rawPath" in event or "httpMethod" in event
    )

    if is_http_proxy:
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/pdf",
                "Content-Disposition": 'inline; filename="generated.pdf"',
            },
            "isBase64Encoded": True,
            "body": encoded_pdf,
        }

    # Return Base64 encoded string directly for direct invocations
    return encoded_pdf


# Alias handler for AWS Lambda Console handler settings
handler = lambda_handler
