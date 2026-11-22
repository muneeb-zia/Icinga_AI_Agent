import os
import sys
import dotenv
from communication_dispatcher import CommunicationDispatcher

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

dotenv.load_dotenv(override=True)

def test_mail(recipient: str):
    print(f"Testing real SMTP email dispatch to: {recipient}")
    print(f"  SMTP_HOST: {os.environ.get('SMTP_HOST')}")
    print(f"  SMTP_PORT: {os.environ.get('SMTP_PORT', 587)}")
    print(f"  SMTP_USER: {os.environ.get('SMTP_USER')}")
    print(f"  SMTP_FROM: {os.environ.get('SMTP_FROM')}")
    
    res = CommunicationDispatcher.dispatch_sla_report_email(
        recipient_email=recipient,
        client_name="Acme Global Corporation",
        pdf_path="enterprise_sla_report.pdf",
        excel_path="enterprise_sla_report.xlsx"
    )
    print("\n--- DISPATCH RESULT ---")
    for k, v in res.items():
        print(f"  {k}: {v}")
    
    if res.get("status") == "DELIVERED" and "LIVE_SMTP" in res.get("delivery_mode", ""):
        print("\nSUCCESS! Real email sent via live SMTP.")
    else:
        print(f"\nResult status: {res.get('status')} | Mode: {res.get('delivery_mode')}")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TEST_RECIPIENT", "client@retailcorp.com")
    test_mail(target)
