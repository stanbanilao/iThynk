import unittest

from ithynk.extractor import extract_fields, mask_id, verify_document_id


class ExtractorTests(unittest.TestCase):
    def test_extracts_expected_fields_from_selectable_pdf_text(self):
        pages = [
            (
                1,
                "Consumer Name: Thando\n"
                "Consumer Surname: Ndlovu\n"
                "ID Number: 9001015009087\n"
                "Contact Number: 0821234567\n"
                "Employer: Example Holdings\n"
                "Status: Signed\n"
                "Status Date: 2026-09-02\n"
                "Reference Number: IDOCS-12345\n",
            )
        ]
        extracted = extract_fields(pages)
        values = {item.field_name: item.value for item in extracted}
        self.assertEqual(values["Consumer Name"], "Thando")
        self.assertEqual(values["Consumer Surname"], "Ndlovu")
        self.assertEqual(values["ID Number"], "9001015009087")
        self.assertEqual(values["Contact Number"], "0821234567")
        self.assertEqual(values["Employer"], "Example Holdings")
        self.assertEqual(values["Status"], "Signed")
        self.assertEqual(values["Status Date"], "2026-09-02")
        self.assertEqual(values["iDocs Reference"], "IDOCS-12345")

    def test_verifies_matching_document_id(self):
        pages = [(1, "ID Number: 9001015009087")]
        extracted = extract_fields(pages)
        status, note = verify_document_id("9001015009087", extracted)
        self.assertEqual(status, "Verified")
        self.assertEqual(note, "")

    def test_flags_mismatched_document_id(self):
        pages = [(1, "ID Number: 9001015009087")]
        extracted = extract_fields(pages)
        status, note = verify_document_id("8001015009087", extracted)
        self.assertEqual(status, "Mismatch")
        self.assertTrue(note)

    def test_masks_id_except_last_four_digits(self):
        self.assertEqual(mask_id("9001015009087"), "*********9087")


if __name__ == "__main__":
    unittest.main()
