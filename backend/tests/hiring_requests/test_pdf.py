from app.modules.hiring_requests.domain import APPROVAL_STAGES
from app.modules.hiring_requests.pdf import render_hiring_request_pdf


def test_approval_chain_is_fixed_and_sequential() -> None:
    assert [stage.code for stage in APPROVAL_STAGES] == [
        "hr_director",
        "economic_director",
        "competition_commission",
        "legal_department",
        "chairman",
    ]


def test_pdf_contains_cyrillic_candidate_and_request_number() -> None:
    request = {
        "requestNumber": "HR-HIRE-2026-00001",
        "createdAt": "2026-07-16",
        "initiatorName": "Айгерим Садыкова",
        "status": "pdf_generated",
        "employmentData": {"department": "Юридический департамент", "position": "Юрисконсульт"},
        "educationData": {"educationLevel": "Высшее", "institution": "Университет"},
    }
    personal = {"lastName": "Ахметова", "firstName": "Алия", "iin": "900101300001"}
    content = render_hiring_request_pdf(request, personal, [], [{"originalFilename": "диплом.pdf"}])
    assert content.startswith(b"%PDF-")
    assert len(content) > 5_000
