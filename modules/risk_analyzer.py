WEIGHTS = {
    'face': 15,
    'plate': 20,
    'plate_candidate': 12,
    'id_keyword': 30,
    'possible_minor': 35,
    'gps_location': 25,
    'email': 8,
    'phone_number': 10,
    'ssn_like': 35,
    'credit_card_like': 35,
    'passport_like': 20,
    'background_object': 5,
    'visual_landmark': 25,
    'visual_address': 25,
    'visual_storefront': 15,
    'visual_street_sign': 12,
    'consent_denied': 35,
    'consent_unverified': 15,
    'pattern_routine_leak': 25,
}

LEVEL_THRESHOLDS = [(20, 'Low'), (50, 'Medium'), (75, 'High'), (100, 'Critical')]


def _level_for(score):
    for threshold, label in LEVEL_THRESHOLDS:
        if score <= threshold:
            return label
    return 'Critical'


def compute_risk(detections):
    """
    Computes holistic privacy risk score (0-100) combining:
    - Base detections (faces, plates, sensitive OCR, background objects, EXIF GPS)
    - Visual location inference (Aspect B)
    - Cross-session recurrence & routine patterns (Aspect A)
    - Per-person consent compliance (Aspect C)
    """
    score = 0
    breakdown = []
    suggestions = []

    # 1. Faces
    faces = detections.get('faces', [])
    if faces:
        pts = WEIGHTS['face'] * len(faces)
        score += pts
        breakdown.append({'category': 'Faces', 'detail': f"{len(faces)} identifiable face(s) detected", 'points': pts})
        suggestions.append('Blur or crop detected faces before posting publicly.')

    # 2. License Plates
    plates = detections.get('plates', [])
    for p in plates:
        w = WEIGHTS.get(p.get('type', 'plate'), WEIGHTS['plate'])
        score += w
        breakdown.append({'category': 'License Plate', 'detail': f"{p.get('type', 'plate')} detected", 'points': w})
    if plates:
        suggestions.append('Blur license plates to prevent vehicle tracking or location inference.')

    # 3. Child Safety
    child_flags = detections.get('child_flags', [])
    minors_flagged = [c for c in child_flags if c.get('flag_for_review')]
    if minors_flagged:
        pts = WEIGHTS['possible_minor'] * len(minors_flagged)
        score += pts
        reasons = {c.get('reason') or c.get('estimated_age_range', 'review needed') for c in minors_flagged}
        breakdown.append({'category': 'Child Safety', 'detail': '; '.join(reasons), 'points': pts})
        suggestions.append('⚠️ Possible minor(s) detected — strongly consider blurring/removing these faces, or confirm you have parental/guardian consent.')

    # 4. OCR / Document text
    ocr = detections.get('ocr', {})
    for finding in ocr.get('findings', []):
        w = WEIGHTS.get(finding.get('type'), 10)
        score += w
        breakdown.append({'category': 'Text / Document', 'detail': f"{finding.get('type')}: {finding.get('match')}", 'points': w})
    if any(f.get('type') == 'id_keyword' for f in ocr.get('findings', [])):
        suggestions.append('An identity document is visible — crop or blur it completely.')
    if any(f.get('type') in ('ssn_like', 'credit_card_like') for f in ocr.get('findings', [])):
        suggestions.append('A number matching an SSN/credit-card pattern was found — remove or blur it immediately.')
    if any(f.get('type') in ('email', 'phone_number') for f in ocr.get('findings', [])):
        suggestions.append('Personal contact details (email/phone) are visible in the image text.')

    # 5. EXIF GPS Metadata
    meta = detections.get('metadata', {})
    if meta.get('has_gps'):
        score += WEIGHTS['gps_location']
        breakdown.append({'category': 'Metadata', 'detail': 'GPS location embedded in EXIF metadata', 'points': WEIGHTS['gps_location']})
        suggestions.append('Strip EXIF/GPS metadata before posting — otherwise your coordinates are embedded in the file.')

    # 6. Background Objects
    bg_objects = detections.get('background_objects', [])
    if bg_objects:
        pts = WEIGHTS['background_object'] * len(bg_objects)
        score += pts
        labels = ', '.join(sorted({o.get('label', '') for o in bg_objects if o.get('label')}))
        breakdown.append({'category': 'Background', 'detail': f"Potentially sensitive items visible: {labels}", 'points': pts})
        suggestions.append('Check the background — screens, mail, or documents can leak sensitive data.')

    # 7. Aspect B: Visual Location Inference
    vis_loc = detections.get('visual_location', {})
    if vis_loc and vis_loc.get('location_revealed'):
        loc_score = vis_loc.get('risk_score', 0)
        if loc_score > 0:
            score += int(loc_score * 0.4)
            landmarks = vis_loc.get('inferred_landmarks', [])
            clues = vis_loc.get('visual_clues', [])
            detail_items = []
            if landmarks:
                detail_items.append(f"Landmark(s): {', '.join([l.get('name', '') for l in landmarks[:2]])}")
            if clues:
                clue_types = {c.get('type', '') for c in clues}
                detail_items.append(f"Visual clues: {', '.join(clue_types)}")

            breakdown.append({
                'category': 'Visual Location',
                'detail': '; '.join(detail_items) if detail_items else 'Visual location clues detected in pixels',
                'points': int(loc_score * 0.4)
            })
            suggestions.append('Visual location inference detected identifiable landmarks, street signs, or storefronts. Blur or crop visual landmarks even if GPS EXIF is removed.')

    # 8. Aspect A: Cross-Session Pattern Risk
    pat_risk = detections.get('pattern_risk', {})
    if pat_risk and pat_risk.get('risk_level') in ('MODERATE', 'HIGH', 'CRITICAL'):
        pts_map = {'MODERATE': 15, 'HIGH': 25, 'CRITICAL': 35}
        pts = pts_map.get(pat_risk.get('risk_level'), 10)
        score += pts
        patterns = pat_risk.get('detected_patterns', [])
        pattern_summaries = [p.get('summary', '') for p in patterns[:2] if p.get('summary')]
        breakdown.append({
            'category': 'Cross-Session Pattern',
            'detail': f"{pat_risk.get('risk_level')} risk: {'; '.join(pattern_summaries) if pattern_summaries else 'Recurring temporal/spatial routine revealed across multiple images'}",
            'points': pts
        })
        suggestions.append('Cross-session analysis reveals recurring routine patterns. Posting multiple images from the same times/locations allows adversaries to map your schedule.')

    # 9. Aspect C: Per-Person Consent Gating
    consent = detections.get('consent', {})
    if consent and not consent.get('can_share', True):
        gated_faces = consent.get('faces_gated', 0)
        decision = consent.get('overall_decision', '')
        if decision == 'PROHIBITED':
            pts = WEIGHTS['consent_denied']
            score += pts
            breakdown.append({
                'category': 'Consent Gating',
                'detail': 'PROHIBITED: Identifiable individual in image explicitly DENIED consent',
                'points': pts
            })
            suggestions.append('⛔ Image contains a person who explicitly denied consent. Do NOT share this image without redacting or obtaining permission.')
        elif gated_faces > 0:
            pts = min(30, WEIGHTS['consent_unverified'] * gated_faces)
            score += pts
            breakdown.append({
                'category': 'Consent Gating',
                'detail': f"{gated_faces} face(s) lack valid consent for requested sharing scope",
                'points': pts
            })
            suggestions.append('Consent gating requires redacting unconsented faces before sharing.')

    score = min(score, 100)
    level = _level_for(score)

    seen = set()
    deduped = []
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            deduped.append(s)

    return {'score': score, 'level': level, 'breakdown': breakdown, 'suggestions': deduped}
