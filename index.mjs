import chromium from "@sparticuz/chromium";
import puppeteer from "puppeteer-core";

export const handler = async (event) => {
  let browser;
  console.log("==============", event);
  try {
    const html = event.html;
    if (!html) {
      throw new Error("html is required");
    }

    browser = await puppeteer.launch({
      args: chromium.args,
      defaultViewport: chromium.defaultViewport,
      executablePath: await chromium.executablePath(),
      headless: chromium.headless,
    });

    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: "networkidle0" });

    const pdfBuffer = await page.pdf({
      format: "A4",
      printBackground: true,
    });

    // ✅ Raw Buffer returned
    return pdfBuffer;
  } finally {
    if (browser) await browser.close();
  }
};
