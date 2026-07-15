import chromium from "@sparticuz/chromium";
import puppeteer from "puppeteer-core";

export const handler = async (event) => {
  let browser;
  console.log("============== Event:", event);

  try {
    // Parse body (works for Function URL + API Gateway)
    const body =
      typeof event?.body === "string"
        ? JSON.parse(event.body)
        : (event?.body ?? {});

    const html = body.html;

    if (!html || typeof html !== "string") {
      throw new Error("html is required");
    }

    // Launch Chromium
    browser = await puppeteer.launch({
      args: chromium.args,
      defaultViewport: chromium.defaultViewport,
      executablePath: await chromium.executablePath(),
      headless: chromium.headless,
    });

    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: "networkidle0" });

    // Generate PDF buffer
    const pdfBuffer = await page.pdf({
      format: "A4",
      printBackground: true,
    });

    // ✅ Return raw Buffer (for Node 24 Lambda)
    return pdfBuffer;
  } finally {
    if (browser) await browser.close();
  }
};
