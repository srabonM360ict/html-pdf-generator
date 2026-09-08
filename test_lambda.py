import json
from lambda_function import lambda_handler

test_event = {
    "body": json.dumps({
        "html": "<html><body><h1 style='color: navy;'>Hello from Python Lambda PDF Generator!</h1><p>Testing payload and output compatibility.</p></body></html>",
        "imageQuality": 0.6,
        "maxImageDimension": 1200,
        "format": "A4",
        "printBackground": True,
        "scale": 1.0
    }),
    "requestContext": {
        "http": {"method": "POST"}
    }
}

if __name__ == "__main__":
    print("Testing Python Lambda handler...")
    response = lambda_handler(test_event)
    print("Response Status Code:", response.get("statusCode"))
    print("Body length (Base64 PDF):", len(response.get("body", "")))
    print("Test completed successfully!")
