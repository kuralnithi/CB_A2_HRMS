"""
Seed Qdrant Cloud with HR Policy documents.
Run: python -m app.ai.seed_qdrant
"""
import os
import sys
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore

# Add the parent directory of 'app' to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.core.config import settings
from app.core.llm import get_embeddings

COLLECTION_NAME = "hr_policies"

# gemini-embedding-001 outputs 3072-dimensional vectors
VECTOR_SIZE = 3072

POLICY_TEXT = """
# Leave Policy

## Paid Leave
All full-time employees are entitled to 20 days of paid leave per year (annual/casual combined).
Casual leave: 10 days per year. Annual/Earned leave: 10 days per year.
Unused earned leave can be carried forward to the next year, up to a maximum of 15 days.
Unused casual leave cannot be carried forward and expires at year-end.

## Sick Leave
Employees are entitled to unlimited sick leave with pay.
However, sick leave of more than 3 consecutive working days requires a medical certificate.
Frequent or patterned sick leave may be reviewed by the HR team.

## Maternity and Paternity Leave
Maternity leave: 26 weeks (6 months) of paid leave for female employees.
Paternity leave: 4 weeks of paid leave for male employees.
Adoption leave: 12 weeks for the primary caregiver.

## Half-Day Leave
Employees may apply for half-day leave (morning or afternoon session).
Half-day leave is deducted as 0.5 days from the casual leave balance.

## Public Holidays
NovaWorks observes 12 public holidays per year as per the company holiday calendar.
Public holidays do not count towards the 20 days of paid leave entitlement.

## Leave Approval
All leave requests must be submitted at least 2 working days in advance (except emergencies).
Leave requests are approved by the reporting manager.
Admin/HR can override leave approvals in exceptional circumstances.

---

# Remote Work Policy

## Work From Home
Employees may work from home up to 3 days per week.
The remaining 2 days must be spent in the office for in-person collaboration.
Fully remote arrangements require VP-level approval.

## Core Hours
All employees must be available during core hours: 10:00 AM to 3:00 PM IST.
Outside core hours, employees may manage their own schedules.
Meetings should be scheduled during core hours whenever possible.

## Equipment
The company provides a laptop and essential peripherals for remote work.
Employees may claim up to $500 every two years for home office setup (monitor, keyboard, chair, etc.).

---

# Expense Reimbursement Policy

## Business Travel
All business travel must be pre-approved by the reporting manager.
Domestic travel: Economy class for flights under 4 hours; Premium economy for longer flights.
International travel requires Director-level approval.

## Meals and Per Diem
Meals during business travel are reimbursed up to $50 per day.
Per diem for domestic travel: $75/day. International travel: $120/day.

## Hardware Purchases
Hardware purchases for work purposes are covered up to $500 every two years.
Requests must be submitted through the IT procurement portal and approved by the manager.

---

# Code of Conduct

## Workplace Behavior
All employees are expected to maintain professional behavior at all times.
Harassment, bullying, discrimination, or intimidation of any kind will not be tolerated.
Violations will be investigated and may result in disciplinary action, including termination.

## Conflict of Interest
Employees must disclose any potential conflicts of interest to HR immediately.
Outside employment, consulting, or board memberships must be reported and approved by HR.

## Confidentiality
All company proprietary information, client data, and trade secrets are strictly confidential.
Employees must not share confidential information outside the organization without authorization.

## Communication
Official communication must use company-approved channels (email, Slack, internal tools).
Public social media posts about the company must comply with the social media policy.

---

# Performance Review Policy

## Review Cycle
Performance reviews are conducted semi-annually in June and December.
Reviews include self-assessment, manager assessment, and 360-degree feedback from peers.

## Criteria
Employees are evaluated on: Technical skills, Collaboration, Initiative, Impact, and Alignment with company values.

## Outcomes
Raises, bonuses, and promotions are determined based on performance review outcomes and company financial health.
High performers may be eligible for stock options and special project assignments.
Employees on Performance Improvement Plans (PIPs) will have 90 days to demonstrate improvement.

---

# Attendance Policy

## Working Hours
Standard working hours are 9:00 AM to 6:00 PM IST with a 1-hour lunch break.
Flexible start times are allowed between 8:00 AM and 10:00 AM, with corresponding end times.

## Late Arrival
Arriving more than 15 minutes after the scheduled start time counts as a late arrival.
Three late arrivals in a month will result in a notification to the reporting manager.
Persistent lateness may affect performance reviews.

## Timekeeping
All employees must log their attendance daily using the HRMS portal.
Failure to log attendance may result in the day being marked as absent.
"""


def seed_qdrant():
    print("Connecting to Qdrant Cloud...")
    client = QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY
    )

    # Recreate collection for a clean state
    if client.collection_exists(COLLECTION_NAME):
        print(f"Deleting existing collection '{COLLECTION_NAME}'...")
        client.delete_collection(COLLECTION_NAME)

    print(f"Creating collection '{COLLECTION_NAME}' with vector size {VECTOR_SIZE}...")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )

    # Write policies to a temp file for the TextLoader
    temp_file = os.path.join(os.path.dirname(__file__), "temp_policies.txt")
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(POLICY_TEXT)

    print("Loading and splitting policies...")
    loader = TextLoader(temp_file, encoding="utf-8")
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n---\n", "\n## ", "\n# ", "\n\n", "\n", " "]
    )
    docs = text_splitter.split_documents(documents)
    print(f"Created {len(docs)} chunks.")

    print("Generating embeddings and uploading to Qdrant...")
    embeddings = get_embeddings()

    QdrantVectorStore.from_documents(
        docs,
        embeddings,
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        collection_name=COLLECTION_NAME,
    )

    print(f"[OK] Seeded Qdrant with {len(docs)} policy chunks.")

    # Clean up temp file
    os.remove(temp_file)


if __name__ == "__main__":
    seed_qdrant()
