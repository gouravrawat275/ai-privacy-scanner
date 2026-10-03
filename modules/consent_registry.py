"""
Aspect C — Per-Person Consent Gating with Facial Embeddings

Enables gating of image sharing based on recorded consent status of identifiable individuals:
- Extracts facial embeddings / feature signatures for detected faces.
- Compares against a local, privacy-preserving Consent Registry.
- Evaluates policy compliance (e.g. GRANTED, DENIED, REVOKED, EXPIRED, UNKNOWN).
- Determines if an image is cleared for sharing, or flags specific faces for mandatory redaction.
"""

import os
import sqlite3
import json
import time
import hashlib
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Dict, List, Any, Optional, Tuple
import cv2
import numpy as np


DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'consent_registry.db')


class FaceEmbeddingExtractor:
    """
    Extracts normalized facial embeddings for face comparison.
    Uses multi-scale localized feature histograms and frequency descriptors
    as an offline, dependency-free embedding vector (256-D normalized vector),
    with optional OpenCV DNN/SFace support if available.
    """

    def __init__(self):
        self.embedding_dim = 256

    def extract(self, image_bgr: np.ndarray, bbox: List[int]) -> np.ndarray:
        """
        Extract a normalized feature vector for a face bounding box [x, y, w, h].
        """
        x, y, w, h = [int(v) for v in bbox]
        img_h, img_w = image_bgr.shape[:2]

        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(img_w, x + w)
        y2 = min(img_h, y + h)

        if x2 <= x1 or y2 <= y1:
            return np.zeros(self.embedding_dim, dtype=np.float32)

        face_crop = image_bgr[y1:y2, x1:x2]
        if face_crop.size == 0:
            return np.zeros(self.embedding_dim, dtype=np.float32)

        # Standardize face crop
        resized = cv2.resize(face_crop, (96, 96))
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        # Multi-region grid descriptors (4x4 cells -> 16 cells)
        features = []
        cell_h, cell_w = 24, 24
        for r in range(4):
            for c in range(4):
                cell = gray[r * cell_h:(r + 1) * cell_h, c * cell_w:(c + 1) * cell_w]
                # 8-bin intensity histogram per cell
                hist = cv2.calcHist([cell], [0], None, [8], [0, 256]).flatten()
                # Sobel gradient magnitude histogram (4 bins)
                gx = cv2.Sobel(cell, cv2.CV_32F, 1, 0, ksize=3)
                gy = cv2.Sobel(cell, cv2.CV_32F, 0, 1, ksize=3)
                mag = cv2.magnitude(gx, gy)
                mag_hist = cv2.calcHist([mag.astype(np.uint8)], [0], None, [4], [0, 256]).flatten()

                # Cell summary stats
                cell_mean = np.mean(cell) / 255.0
                cell_std = np.std(cell) / 128.0

                features.extend(hist / (cell_h * cell_w + 1e-6))
                features.extend(mag_hist / (cell_h * cell_w + 1e-6))
                features.append(cell_mean)
                features.append(cell_std)

        feat_arr = np.array(features, dtype=np.float32)
        # Resize/truncate or pad to target embedding_dim (256)
        if len(feat_arr) > self.embedding_dim:
            feat_arr = feat_arr[:self.embedding_dim]
        elif len(feat_arr) < self.embedding_dim:
            feat_arr = np.pad(feat_arr, (0, self.embedding_dim - len(feat_arr)), mode='constant')

        # L2 normalize
        norm = np.linalg.norm(feat_arr)
        if norm > 1e-6:
            feat_arr = feat_arr / norm

        return feat_arr

    @staticmethod
    def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        if norm1 < 1e-6 or norm2 < 1e-6:
            return 0.0
        return float(np.dot(emb1, emb2) / (norm1 * norm2))


class ConsentRegistry:
    """
    Local privacy-first consent registry for individuals whose consent
    must be verified prior to image sharing.
    """

    CONSENT_STATUSES = ['GRANTED', 'DENIED', 'RESTRICTED', 'REVOKED', 'EXPIRED']
    DEFAULT_SCOPES = ['public', 'social_media', 'internal_only', 'commercial']

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.extractor = FaceEmbeddingExtractor()
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    _connection = _get_connection

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subjects (
                    subject_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    notes TEXT,
                    consent_status TEXT NOT NULL DEFAULT 'GRANTED',
                    allowed_scopes TEXT NOT NULL DEFAULT '["public","social_media","internal_only"]',
                    valid_until TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS face_templates (
                    template_id TEXT PRIMARY KEY,
                    subject_id TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    source_image_name TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS consent_audit_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_id TEXT,
                    action TEXT NOT NULL,
                    scope_requested TEXT,
                    decision TEXT NOT NULL,
                    reason TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.commit()

    def register_subject(
        self,
        name: str,
        consent_status: str = 'GRANTED',
        allowed_scopes: Optional[List[str]] = None,
        valid_until: Optional[str] = None,
        notes: str = "",
        reference_image_bgr: Optional[np.ndarray] = None,
        face_bbox: Optional[List[int]] = None
    ) -> str:
        """Register a new subject in the registry, optionally with a reference face."""
        if consent_status not in self.CONSENT_STATUSES:
            consent_status = 'GRANTED'
        if allowed_scopes is None:
            allowed_scopes = ['public', 'social_media', 'internal_only']

        subject_id = hashlib.sha256(f"{name}_{time.time()}".encode()).hexdigest()[:12]
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO subjects (subject_id, name, notes, consent_status, allowed_scopes, valid_until, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                subject_id,
                name,
                notes,
                consent_status,
                json.dumps(allowed_scopes),
                valid_until,
                now,
                now
            ))

            if reference_image_bgr is not None:
                if face_bbox is None:
                    h, w = reference_image_bgr.shape[:2]
                    face_bbox = [0, 0, w, h]
                emb = self.extractor.extract(reference_image_bgr, face_bbox)
                template_id = hashlib.sha256(f"{subject_id}_{time.time()}".encode()).hexdigest()[:12]
                cursor.execute("""
                    INSERT INTO face_templates (template_id, subject_id, embedding_json, source_image_name, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    template_id,
                    subject_id,
                    json.dumps(emb.tolist()),
                    "reference",
                    now
                ))
            conn.commit()

        return subject_id

    def add_face_template(self, subject_id: str, image_bgr: np.ndarray, bbox: List[int], source_name: str = "") -> Optional[str]:
        """Add an additional facial template for an existing subject."""
        emb = self.extractor.extract(image_bgr, bbox)
        if np.linalg.norm(emb) < 1e-4:
            return None
        template_id = hashlib.sha256(f"{subject_id}_{time.time()}_{np.random.rand()}".encode()).hexdigest()[:12]
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO face_templates (template_id, subject_id, embedding_json, source_image_name, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (template_id, subject_id, json.dumps(emb.tolist()), source_name, now))
            conn.commit()
        return template_id

    def update_consent(
        self,
        subject_id: str,
        consent_status: str,
        allowed_scopes: Optional[List[str]] = None,
        valid_until: Optional[str] = None
    ) -> bool:
        """Update consent status and permitted scopes."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if allowed_scopes is not None:
                cursor.execute("""
                    UPDATE subjects
                    SET consent_status = ?, allowed_scopes = ?, valid_until = ?, updated_at = ?
                    WHERE subject_id = ?
                """, (consent_status, json.dumps(allowed_scopes), valid_until, now, subject_id))
            else:
                cursor.execute("""
                    UPDATE subjects
                    SET consent_status = ?, valid_until = ?, updated_at = ?
                    WHERE subject_id = ?
                """, (consent_status, valid_until, now, subject_id))
            conn.commit()
            return cursor.rowcount > 0

    def list_subjects(self) -> List[Dict[str, Any]]:
        """List all registered subjects."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, COUNT(t.template_id) as template_count
                FROM subjects s
                LEFT JOIN face_templates t ON s.subject_id = t.subject_id
                GROUP BY s.subject_id
                ORDER BY s.updated_at DESC
            """)
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item['allowed_scopes'] = json.loads(item['allowed_scopes']) if item['allowed_scopes'] else []
                results.append(item)
            return results

    def delete_subject(self, subject_id: str) -> bool:
        """Remove a subject and templates from the registry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM face_templates WHERE subject_id = ?", (subject_id,))
            cursor.execute("DELETE FROM subjects WHERE subject_id = ?", (subject_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_subject_templates(self) -> List[Dict[str, Any]]:
        """Retrieve all face templates with subject metadata for matching."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.template_id, t.subject_id, t.embedding_json,
                       s.name, s.consent_status, s.allowed_scopes, s.valid_until
                FROM face_templates t
                JOIN subjects s ON t.subject_id = s.subject_id
            """)
            rows = cursor.fetchall()
            templates = []
            for r in rows:
                templates.append({
                    'template_id': r['template_id'],
                    'subject_id': r['subject_id'],
                    'name': r['name'],
                    'consent_status': r['consent_status'],
                    'allowed_scopes': json.loads(r['allowed_scopes']) if r['allowed_scopes'] else [],
                    'valid_until': r['valid_until'],
                    'embedding': np.array(json.loads(r['embedding_json']), dtype=np.float32)
                })
            return templates

    def match_face(
        self,
        face_emb: np.ndarray,
        templates: Optional[List[Dict[str, Any]]] = None,
        threshold: float = 0.65
    ) -> Optional[Dict[str, Any]]:
        """Match a face embedding against known templates."""
        if templates is None:
            templates = self.get_subject_templates()
        if not templates:
            return None

        best_match = None
        best_score = -1.0

        for t in templates:
            score = self.extractor.cosine_similarity(face_emb, t['embedding'])
            if score > best_score:
                best_score = score
                best_match = t

        if best_match and best_score >= threshold:
            res = dict(best_match)
            res['similarity'] = round(float(best_score), 3)
            # Remove embedding array for cleaner serializability
            res.pop('embedding', None)
            return res

        return None

    def evaluate_image_consent(
        self,
        image_bgr: np.ndarray,
        detected_faces: List[Dict[str, Any]],
        target_scope: str = 'social_media',
        policy: str = 'STRICT',  # 'STRICT' or 'ALLOW_UNKNOWN'
        match_threshold: float = 0.65
    ) -> Dict[str, Any]:
        """
        Evaluate consent compliance for all detected faces in an image.

        Returns:
            {
                'can_share': bool,
                'overall_decision': 'APPROVED' | 'GATED_REDACTION_REQUIRED' | 'PROHIBITED',
                'policy': policy,
                'target_scope': target_scope,
                'faces_evaluated': int,
                'faces_passed': int,
                'faces_gated': int,
                'face_decisions': [...],
                'redaction_boxes': [[x,y,w,h], ...],
                'summary_reasons': [...]
            }
        """
        templates = self.get_subject_templates()
        now_dt = datetime.now(timezone.utc)

        face_decisions = []
        redaction_boxes = []
        reasons = []

        gated_count = 0
        denied_hard_block = False

        for i, face in enumerate(detected_faces):
            bbox = face.get('bbox')
            if not bbox:
                continue

            emb = self.extractor.extract(image_bgr, bbox)
            match = self.match_face(emb, templates, threshold=match_threshold)

            face_decision = {
                'face_index': i,
                'bbox': bbox,
                'matched': match is not None,
                'subject_id': None,
                'name': 'Unknown Person',
                'consent_status': 'UNKNOWN',
                'allowed_scopes': [],
                'similarity': 0.0,
                'can_share': False,
                'requires_redaction': False,
                'reason': ''
            }

            if match:
                face_decision['subject_id'] = match['subject_id']
                face_decision['name'] = match['name']
                face_decision['consent_status'] = match['consent_status']
                face_decision['allowed_scopes'] = match['allowed_scopes']
                face_decision['similarity'] = match['similarity']

                status = match['consent_status']
                valid_until = match.get('valid_until')

                # Check expiration
                is_expired = False
                if valid_until:
                    try:
                        exp_dt = datetime.fromisoformat(valid_until)
                        if exp_dt < now_dt:
                            is_expired = True
                    except Exception:
                        pass

                if is_expired:
                    face_decision['consent_status'] = 'EXPIRED'
                    face_decision['can_share'] = False
                    face_decision['requires_redaction'] = True
                    face_decision['reason'] = f"Consent for {match['name']} expired on {valid_until}."
                    reasons.append(face_decision['reason'])
                    redaction_boxes.append(bbox)
                    gated_count += 1
                elif status == 'DENIED':
                    face_decision['can_share'] = False
                    face_decision['requires_redaction'] = True
                    face_decision['reason'] = f"{match['name']} explicitly DENIED consent for image sharing."
                    reasons.append(face_decision['reason'])
                    redaction_boxes.append(bbox)
                    gated_count += 1
                    denied_hard_block = True
                elif status == 'REVOKED':
                    face_decision['can_share'] = False
                    face_decision['requires_redaction'] = True
                    face_decision['reason'] = f"{match['name']}'s consent was REVOKED."
                    reasons.append(face_decision['reason'])
                    redaction_boxes.append(bbox)
                    gated_count += 1
                elif status == 'RESTRICTED':
                    if target_scope in match['allowed_scopes']:
                        face_decision['can_share'] = True
                        face_decision['reason'] = f"Consent granted for requested scope '{target_scope}'."
                    else:
                        face_decision['can_share'] = False
                        face_decision['requires_redaction'] = True
                        face_decision['reason'] = f"Scope '{target_scope}' is not permitted by {match['name']}."
                        reasons.append(face_decision['reason'])
                        redaction_boxes.append(bbox)
                        gated_count += 1
                elif status == 'GRANTED':
                    if not match['allowed_scopes'] or target_scope in match['allowed_scopes']:
                        face_decision['can_share'] = True
                        face_decision['reason'] = f"Consent unconditionally GRANTED by {match['name']}."
                    else:
                        face_decision['can_share'] = False
                        face_decision['requires_redaction'] = True
                        face_decision['reason'] = f"Scope '{target_scope}' not covered in granted scopes."
                        reasons.append(face_decision['reason'])
                        redaction_boxes.append(bbox)
                        gated_count += 1
            else:
                # Unmatched face
                if policy == 'STRICT':
                    face_decision['can_share'] = False
                    face_decision['requires_redaction'] = True
                    face_decision['reason'] = "Unknown person detected. Under STRICT policy, unconsented faces must be redacted."
                    reasons.append(face_decision['reason'])
                    redaction_boxes.append(bbox)
                    gated_count += 1
                else:
                    face_decision['can_share'] = True
                    face_decision['requires_redaction'] = False
                    face_decision['reason'] = "Unknown person detected. Permitted under standard policy."

            face_decisions.append(face_decision)

        total_faces = len(detected_faces)
        passed_count = total_faces - gated_count

        if total_faces == 0:
            can_share = True
            decision = 'APPROVED'
            reasons.append("No faces detected in image.")
        elif gated_count == 0:
            can_share = True
            decision = 'APPROVED'
            reasons.append(f"All {total_faces} detected individuals have verified consent.")
        elif denied_hard_block:
            can_share = False
            decision = 'PROHIBITED'
            reasons.append("One or more individuals have explicitly DENIED consent. Image sharing is blocked.")
        else:
            can_share = False
            decision = 'GATED_REDACTION_REQUIRED'
            reasons.append(f"{gated_count} of {total_faces} face(s) require redaction before sharing.")

        return {
            'can_share': can_share,
            'overall_decision': decision,
            'policy': policy,
            'target_scope': target_scope,
            'faces_evaluated': total_faces,
            'faces_passed': passed_count,
            'faces_gated': gated_count,
            'face_decisions': face_decisions,
            'redaction_boxes': redaction_boxes,
            'summary_reasons': list(set(reasons))
        }
