import re
import cv2

try:
    import pytesseract
    _TESSERACT_OK = True
except ImportError:
    _TESSERACT_OK = False

try:
    import winocr
    _WINOCR_OK = True
except ImportError:
    _WINOCR_OK = False

ID_KEYWORDS = [
    'passport', "driver's license", 'drivers license', 'driving licence',
    'identity card', 'id card', 'national id', 'social security', 'aadhaar',
    'aadhar', 'date of birth', 'd.o.b', 'dob:', 'ssn', 'license', 'licence'
]
PATTERNS = {
    'email': r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+',
    'phone_number': r'\b(?:(?:\+?1\s*(?:[.-]\s*)?)?(?:\(\s*([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9])\s*\)|([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9]))\s*(?:[.-]\s*)?)?([2-9]1[02-9]|[2-9][02-9]1|[2-9][02-9]{2})\s*(?:[.-]\s*)?([0-9]{4})\b',
    'ssn_like': r'\b\d{3}-\d{2}-\d{4}\b',
    'credit_card_like': r'\b(?:\d{4}[ -]?){3}\d{4}\b',
    'passport_like': r'\b[A-Z]{1,2}\d{6,9}\b',
    'plate_like': r'\b[A-Z]{2}[0-9]{2}\s?[A-Z]{1,2}\s?[0-9]{4}\b'
}


class OCRExtractor:

    def __init__(self):
        self.enabled = _TESSERACT_OK or _WINOCR_OK
        if not self.enabled:
            print('[OCRExtractor] Neither pytesseract nor winocr available — OCR text scanning disabled.')

    def extract(self, image_bgr):
        if not self.enabled:
            return {'enabled': False, 'raw_text': '', 'findings': []}

        text = ""
        ocr_error = None
        # 1. Try winocr on Windows first if available
        if _WINOCR_OK:
            try:
                res = winocr.recognize_cv2_sync(image_bgr)
                text = res.get('text', '') if isinstance(res, dict) else str(res)
            except Exception as exc:
                text = ""
                ocr_error = str(exc)

        # 2. Try pytesseract as fallback or alternative
        if not text and _TESSERACT_OK:
            img_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            try:
                text = pytesseract.image_to_string(img_rgb)
            except Exception as exc:
                ocr_error = str(exc)

        if not text:
            result = {'enabled': True, 'raw_text': '', 'findings': []}
            if ocr_error:
                result['error'] = ocr_error
            return result

        findings = []
        lower = text.lower()
        for kw in ID_KEYWORDS:
            if kw in lower:
                findings.append({'type': 'id_keyword', 'match': kw})
        for name, pattern in PATTERNS.items():
            for m in re.finditer(pattern, text):
                findings.append({'type': name, 'match': m.group()})

        return {'enabled': True, 'raw_text': text, 'findings': findings}
