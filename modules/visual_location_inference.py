"""
Aspect B — Visual Location Inference Independent of Metadata

Infers a probable capture location, or a location-revealing risk flag,
from the visual content of an image (recognized landmarks, storefront or
street-sign text extracted via OCR, distinctive architectural features)
independently of, and in addition to, any embedded GPS metadata — including
when that metadata is absent or has already been stripped.
"""

import re

# --- Known landmark patterns (extensible; local-only reference data) ---
# Each entry: (keywords to match in OCR text, inferred location label, confidence)
LANDMARK_KEYWORDS = [
    # Famous landmarks
    (['eiffel', 'tour eiffel'], 'Paris, France (Eiffel Tower area)', 0.9),
    (['statue of liberty', 'liberty island'], 'New York, USA (Statue of Liberty)', 0.9),
    (['big ben', 'westminster', 'houses of parliament'], 'London, UK (Westminster)', 0.85),
    (['times square'], 'New York, USA (Times Square)', 0.85),
    (['colosseum', 'coliseum', 'colosseo'], 'Rome, Italy (Colosseum)', 0.85),
    (['taj mahal'], 'Agra, India (Taj Mahal)', 0.9),
    (['golden gate'], 'San Francisco, USA (Golden Gate)', 0.85),
    (['sydney opera', 'opera house sydney'], 'Sydney, Australia (Opera House)', 0.85),
    (['machu picchu'], 'Cusco Region, Peru (Machu Picchu)', 0.9),
    (['burj khalifa'], 'Dubai, UAE (Burj Khalifa)', 0.85),
    (['tower bridge'], 'London, UK (Tower Bridge)', 0.8),
    (['central park'], 'New York, USA (Central Park)', 0.7),
    (['white house'], 'Washington D.C., USA', 0.75),
    (['kremlin'], 'Moscow, Russia (Kremlin)', 0.8),
    (['great wall'], 'Beijing region, China (Great Wall)', 0.8),
    (['christ the redeemer', 'cristo redentor'], 'Rio de Janeiro, Brazil', 0.85),
]

# Address / street-sign patterns
ADDRESS_PATTERNS = [
    # US-style addresses
    re.compile(r'\b\d{1,5}\s+(?:N|S|E|W|North|South|East|West)?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*'
               r'\s+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Way|Ct|Court|Pl|Place)\b',
               re.IGNORECASE),
    # Road/highway signs
    re.compile(r'\b(?:Interstate|I-|US-|SR-|Route|Hwy)\s*\d{1,4}\b', re.IGNORECASE),
    # ZIP codes (US)
    re.compile(r'\b\d{5}(?:-\d{4})?\b'),
    # UK postcodes
    re.compile(r'\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b', re.IGNORECASE),
    # Indian PIN codes
    re.compile(r'\b\d{6}\b'),
]

# Business-name / storefront patterns that reveal location
BUSINESS_PATTERNS = [
    re.compile(r'\b(?:Starbucks|McDonald\'?s|Walmart|Target|Costco|CVS|Walgreens|'
               r'7-Eleven|KFC|Subway|Burger King|Dunkin|Taco Bell|Pizza Hut|'
               r'Domino\'?s|Whole Foods|Trader Joe\'?s|Aldi|Lidl|Tesco|Sainsbury\'?s|'
               r'Carrefour|Metro|IKEA)\b', re.IGNORECASE),
]

# Street-sign keywords
STREET_SIGN_KEYWORDS = [
    'stop', 'yield', 'one way', 'no parking', 'speed limit',
    'exit', 'ramp', 'crossing', 'school zone',
]


class VisualLocationInference:
    """
    Infers location-revealing risk from an image's visual content,
    operating independently of and in addition to any GPS metadata.
    """

    def __init__(self, ocr_extractor=None):
        self.ocr_extractor = ocr_extractor

    def analyze(self, image_bgr, ocr_result=None):
        return self._analyze_impl(image_bgr, ocr_result)

    def infer(self, image_bgr, ocr_result=None):
        return self._analyze_impl(image_bgr, ocr_result)

    def _analyze_impl(self, image_bgr, ocr_result=None):
        """
        Analyze image for visual location cues.

        Args:
            image_bgr: OpenCV BGR image array
            ocr_result: Pre-computed OCR result dict (if already available)

        Returns:
            dict with location findings independent of metadata
        """
        # Get OCR text if not already provided
        if ocr_result is None and self.ocr_extractor is not None:
            ocr_result = self.ocr_extractor.extract(image_bgr)

        raw_text = ''
        if ocr_result and ocr_result.get('enabled'):
            raw_text = ocr_result.get('raw_text', '')

        findings = []
        location_bucket = None
        overall_confidence = 0.0

        # --- 1. Landmark matching ---
        landmark_result = self._match_landmarks(raw_text)
        if landmark_result:
            findings.append(landmark_result)
            overall_confidence = max(overall_confidence, landmark_result['confidence'])
            location_bucket = landmark_result.get('inferred_location', '')

        # --- 2. Address / street-sign text extraction ---
        address_results = self._extract_addresses(raw_text)
        for addr in address_results:
            findings.append(addr)
            overall_confidence = max(overall_confidence, addr['confidence'])

        # --- 3. Business name matching ---
        business_results = self._match_businesses(raw_text)
        for biz in business_results:
            findings.append(biz)
            overall_confidence = max(overall_confidence, biz['confidence'])

        # --- 4. Street sign detection ---
        sign_results = self._detect_street_signs(raw_text)
        for sign in sign_results:
            findings.append(sign)

        # --- 5. Scene-type labels (architectural / environmental cues) ---
        scene_labels = self._classify_scene_cues(raw_text, image_bgr)

        has_visual_location_risk = len(findings) > 0
        risk_score = min(60, int(overall_confidence * 40) + len(findings) * 8)

        return {
            'has_visual_location_risk': has_visual_location_risk,
            'location_revealed': has_visual_location_risk,
            'risk_score': risk_score,
            'findings': findings,
            'location_bucket': location_bucket,
            'scene_labels': scene_labels,
            'overall_confidence': round(overall_confidence, 3),
            'explanation': self._explain(findings) if findings else
                           "No location-revealing content detected in the image's visual content."
        }

    def _match_landmarks(self, text):
        """Match OCR text against known landmark keywords."""
        if not text:
            return None
        lower = text.lower()
        for keywords, location, conf in LANDMARK_KEYWORDS:
            for kw in keywords:
                if kw in lower:
                    return {
                        'type': 'landmark_match',
                        'matched_keyword': kw,
                        'inferred_location': location,
                        'confidence': conf,
                        'detail': f"Landmark text '{kw}' detected — likely location: {location}"
                    }
        return None

    def _extract_addresses(self, text):
        """Extract address-like patterns from OCR text."""
        results = []
        if not text:
            return results
        for pattern in ADDRESS_PATTERNS:
            for match in pattern.finditer(text):
                matched = match.group().strip()
                if len(matched) < 5:  # skip very short matches
                    continue
                results.append({
                    'type': 'address_detected',
                    'matched_text': matched,
                    'confidence': 0.7,
                    'detail': f"Address-like text detected: '{matched}' — may reveal the capture location"
                })
        return results[:5]  # cap at 5 findings

    def _match_businesses(self, text):
        """Match against known business/chain names."""
        results = []
        if not text:
            return results
        for pattern in BUSINESS_PATTERNS:
            for match in pattern.finditer(text):
                name = match.group().strip()
                results.append({
                    'type': 'business_name',
                    'matched_text': name,
                    'confidence': 0.5,
                    'detail': f"Business name '{name}' visible — combined with other cues, "
                              f"this could narrow down the location"
                })
        seen = set()
        deduped = []
        for r in results:
            key = r['matched_text'].lower()
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped[:3]

    def _detect_street_signs(self, text):
        """Detect street-sign text that implies a specific location context."""
        results = []
        if not text:
            return results
        lower = text.lower()
        for kw in STREET_SIGN_KEYWORDS:
            if kw in lower:
                results.append({
                    'type': 'street_sign',
                    'matched_text': kw,
                    'confidence': 0.3,
                    'detail': f"Street sign text '{kw}' detected in image"
                })
        return results[:3]

    def _classify_scene_cues(self, text, image_bgr):
        """
        Basic scene classification from visual/text cues.
        Returns list of scene labels.
        """
        labels = []
        if not text:
            return labels
        lower = text.lower()

        scene_map = {
            'residential': ['apartment', 'house', 'home', 'residence', 'villa',
                          'condo', 'flat', 'duplex'],
            'commercial': ['shop', 'store', 'mall', 'market', 'plaza', 'center',
                         'restaurant', 'cafe', 'bar', 'hotel'],
            'educational': ['school', 'university', 'college', 'academy', 'campus',
                          'library', 'institute'],
            'medical': ['hospital', 'clinic', 'pharmacy', 'medical', 'doctor',
                       'dental', 'health'],
            'transportation': ['airport', 'station', 'terminal', 'bus stop',
                             'train', 'metro', 'subway', 'taxi', 'uber', 'lyft'],
            'government': ['police', 'court', 'city hall', 'government', 'embassy',
                         'consulate', 'post office'],
            'religious': ['church', 'mosque', 'temple', 'synagogue', 'cathedral',
                        'chapel'],
            'recreational': ['park', 'gym', 'pool', 'beach', 'playground',
                           'stadium', 'arena', 'theater', 'cinema'],
        }

        for label, keywords in scene_map.items():
            for kw in keywords:
                if kw in lower:
                    labels.append(label)
                    break

        return list(set(labels))

    @staticmethod
    def _explain(findings):
        """Generate a human-readable explanation of visual location findings."""
        lines = ["📍 Visual Location Inference detected location-revealing content:"]
        for f in findings:
            lines.append(f"  • [{f['type']}] {f['detail']}")
        lines.append("")
        lines.append("This information was extracted from the image's visual content, "
                      "NOT from metadata. Stripping EXIF data alone does not prevent "
                      "this type of location exposure.")
        return "\n".join(lines)


VisualLocationInferrer = VisualLocationInference
