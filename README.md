# 🛡️ AI Privacy Risk Scanner

Scan a photo **before** you post it. Detects faces, license plates,
visible ID documents, possible minors, and embedded GPS metadata; scores
the overall privacy risk; and helps you blur or strip what you don't
want public — all running locally on your own machine.

This exists to reduce the chance of a photo accidentally exposing
something (a face, a plate, a document, your location) that could later
be used to identify, track, harass, or blackmail you or someone else in
the picture.

Login-gated with its own accounts — sign up like you would on any
site, email as your username — and keeps a local dashboard of your
past scans (metadata only — never the images) — see Accounts &
Dashboard below.

## What it is / isn't

- **It detects, it doesn't identify.** Every model here answers "is
  there a face/plate/document *here*?" — none of them attempt to
  recognize *who* a specific person is. There's no facial-recognition
  matching or identity lookup anywhere in this codebase.
- **It's a local pre-upload checklist, not a guarantee.** Treat the risk
  score and suggestions as a helpful second pass before you post, not
  as proof an image is 100% safe.
- **Age estimation is approximate, on purpose conservative, and always
  paired with a "please double-check" note.** See the Child Safety
  Detector section below before you rely on it.

---

## 🌟 Advanced Patent-Disclosed Features (Full Working Implementation)

The system extends baseline single-image scanning with five patent-disclosed privacy defense technologies:

1. **Aspect A: Cross-Session Pattern Risk Analysis (`modules/pattern_risk_engine.py`, `ui/pattern_page.py`)**
   - Evaluates accumulated non-identifying scan history over rolling 30-day windows.
   - Detects habit/routine exposure, temporal patterns (day-of-week, time-of-day), recurring coarse location buckets (~1km grid), and frequent background objects.
   - Alerts the operator when multiple seemingly benign photos together reveal an identifiable routine.

2. **Aspect B: Visual Location Inference Independent of Metadata (`modules/visual_location_inference.py`)**
   - Infers capture location directly from pixel contents (landmarks, addresses, street signs, storefronts, architectural cues).
   - Operates even when EXIF GPS coordinates are absent or have been stripped.
   - Warns users when visual landmarks leak whereabouts regardless of metadata removal.

3. **Aspect C: Per-Person Consent Gating with Facial Embeddings (`modules/consent_registry.py`, `ui/consent_page.py`)**
   - Privacy-preserving 256-D facial feature vectors matched against an offline local SQLite Consent Registry.
   - Enforces per-person status (`GRANTED`, `DENIED`, `RESTRICTED`, `REVOKED`, `EXPIRED`) across distribution scopes (`public`, `social_media`, `internal_only`, `commercial`).
   - Automatically gates sharing or mandates targeted redaction for unconsented individuals.

4. **Aspect D: Cryptographically Reversible Redaction (`modules/crypto_redaction.py`, `ui/crypto_page.py`)**
   - Reversibly obscures flagged regions (faces, license plates, sensitive documents) using visual filters.
   - Seals pristine original pixels inside an authenticated **AES-256-GCM** envelope embedded directly in PNG metadata or standalone `.privpack` sidecars.
   - Only authorized holders of the password or 256-bit AES key can restore the 100% bit-exact original image.

5. **Aspect E: Pre-Capture Live Privacy Guard & Viewfinder (`ui/live_camera_page.py`)**
   - Evaluates privacy risks in real-time **before** capturing or saving an image.
   - Features a camera viewfinder, real-time risk HUD, bounding-box overlays, and live consent status tags.
   - Provides instant operator guidance (e.g. framing adjustments, angle changes) and 1-click Safe Capture with automatic cryptographic locking.

---

## System architecture

```
Register/Login → User Upload → AI Scanner (orchestrator) → Detection Module ─┐
                                                           → OCR Extractor    ├─→ Risk Analyzer → UI Suggestions → Redact → Safe Post → (logged to) Dashboard
                                                           → Child Safety Det ─┘
                                                           → Metadata Scanner ─┘
```

- **Register/Login** (`app.py` + `streamlit-authenticator`) — gates
  everything below it; nothing runs unauthenticated. Sign up or log in,
  same tabbed screen. See Accounts & Dashboard.
- **User Upload** — a photo picked on the Scanner page, or POSTed to the
  optional REST API (its own bearer-token login, same underlying
  accounts).
- **AI Scanner** (`modules/scanner.py`) — orchestrates every detector
  and hands the combined result to the Risk Analyzer.
- **Detection Module** (`modules/detection_module.py`) — faces, plates,
  and (optionally) general background objects.
- **OCR Extractor** (`modules/ocr_extractor.py`) — text extraction +
  sensitive-pattern matching (ID keywords, emails, phone numbers,
  SSN/credit-card-shaped numbers).
- **Child Safety Detector** (`modules/child_safety_detector.py`) —
  conservative age-bracket flagging per detected face.
- **Metadata Scanner** (`modules/metadata_scanner.py`) — EXIF/GPS
  detection and stripping (bonus module, beyond the original spec, but
  one of the highest-value/lowest-effort privacy wins — phone photos
  routinely embed exact GPS coordinates).
- **Risk Analyzer** (`modules/risk_analyzer.py`) — weighted 0–100 score,
  severity level, per-finding breakdown, and plain-language suggestions.
- **Scanner page** (`ui/scanner_page.py`) — shows all of the above and
  lets you select regions to blur, strip metadata, and export a "safe"
  copy. Every scan's metadata (not the image) is logged via
  `modules/scan_history.py`.
- **Dashboard page** (`ui/dashboard_page.py`) — your own scan history:
  totals, average risk, a breakdown chart, and a recent-scans table.

### Flowchart

```
 Start
   │
   ▼
 Sign up (new) ──► account created ──┐
   │                                  │
   ▼                                  ▼
 Log in ◄─────────────────────────────┘
   │
   ▼
 Upload Image
   │
   ▼
 AI Scan  (Detection + OCR + Child Safety + Metadata, in parallel)
   │
   ▼
 Risk Score  (0–100, Low/Medium/High/Critical)
   │
   ▼
 Suggestions  (what to blur / strip, and why)
   │
   ▼
 Accept ──────────────► Safe Post (download redacted image) ──► logged to Dashboard
   │
   └── Reject → back to Upload

 (Logout, from anywhere, via the sidebar → back to Log in)
```

---

## Modules & algorithms

| Module | File | Approach |
|---|---|---|
| Detection Module | `modules/detection_module.py` | **Face:** Haar Cascade by default (zero downloads); auto-upgrades to a DNN detector (ResNet-10 SSD) when `scripts/download_models.py` has been run — substantially more robust on real photos (measured during development: Haar found 0 faces on a real test photo where the DNN backend found 1 at 79% confidence). **Plate:** Haar Cascade (`haarcascade_russian_plate_number.xml`) with a contour/aspect-ratio fallback. **Background:** optional YOLOv8 (`ultralytics`) |
| OCR Extractor | `modules/ocr_extractor.py` | Tesseract OCR + regex/keyword matching for ID documents, emails, phone numbers, SSN- and credit-card-shaped numbers |
| Child Safety Detector | `modules/child_safety_detector.py` | Optional Caffe age-classifier (8 age buckets) run per detected face; **defaults to "flag for manual review" when the model isn't installed**, rather than silently skipping the check |
| Metadata Scanner | `modules/metadata_scanner.py` | PIL EXIF parsing, GPS tag detection, metadata stripping |
| Risk Analyzer | `modules/risk_analyzer.py` | Weighted rule-based scoring across every finding → score + severity + suggestions |
| Scan History | `modules/scan_history.py` | SQLite log of past scans (score, level, finding counts — never the image or extracted text), keyed per-user |
| Scanner / Dashboard pages | `ui/scanner_page.py`, `ui/dashboard_page.py` | Streamlit, behind the login gate in `app.py`: upload → annotated preview → risk panel → per-region blur checkboxes → safe-image export, plus a history view of your own past scans |

Why Haar Cascades are still the *default* for faces/plates rather than
DNN-by-default: Haar ships **inside** `opencv-python`, so detection
works immediately after `pip install`, with no model downloads, no GPU,
and no flaky first-run network dependency. Run
`scripts/download_models.py` once and `FaceDetector` automatically
switches to the much stronger DNN backend — no code changes needed.
YOLO is wired in as a further optional upgrade for background-object
detection since it needs a much heavier dependency (PyTorch) that not
everyone wants installed.

---

## Setup

### 1. Python dependencies

```bash
python3 -m venv .venv && source .venv/bin/activate    # optional but recommended
pip install -r requirements.txt
```

### 2. Tesseract OCR (system binary — required for the OCR Extractor)

`pytesseract` is a wrapper; it needs the actual Tesseract binary installed:

- **Ubuntu/Debian:** `sudo apt-get install tesseract-ocr`
- **macOS:** `brew install tesseract`
- **Windows:** install from the [UB-Mannheim Tesseract build](https://github.com/UB-Mannheim/tesseract/wiki) and ensure it's on your `PATH`

Without it, the app still runs — OCR findings are just skipped, and
you'll see a console notice.

### 3. (Recommended) Better face detection + child-safety age model

```bash
python3 scripts/download_models.py
```

One command, fetches two independent things into `models/`:

- The **DNN face detector** (~10MB) — recommended. `FaceDetector` picks
  it up automatically and switches from the bundled Haar cascade to this
  much more reliable backend, no config needed. This is the single
  biggest accuracy upgrade available in the project.
- The **age-classifier** (~44MB) — optional. Skip it if you're fine
  with faces always being flagged for manual review instead of getting
  an automated age estimate (a perfectly reasonable choice — see the
  caveats below).

Each downloads and verifies independently — if one fails (or you'd
rather not fetch it), the app still runs fully using its fallback for
just that piece.

### 4. (Optional) Background object detection

```bash
pip install ultralytics
```

Adds YOLOv8 for flagging background items (laptops, phones, screens,
other bystanders). Heavy dependency (installs PyTorch) — skip it if
you don't need this layer.

### 5. Set up your login

There is no default username or password. Start the app and use the
**Create Account** tab; successful registration signs you in and opens
the scanner. Existing users can log in to open the scanner directly.
Alternatively, create an account before launch with:

```bash
python3 scripts/manage_users.py add <username> "<Full Name>" <email>
```

`auth_config.yaml` stores password hashes and the API signing key and is
gitignored. On Streamlit Community Cloud, the first account can be
created from the sign-up tab; accounts stored in the app's local
filesystem may need to be recreated after a rebuild.

Need more accounts? Anyone who can reach the app can create their own
via the "Sign up" tab (or `POST /register` on the API) — no CLI step
required. `scripts/manage_users.py add <username> "<Full Name>" <email>`
still works too, for adding an account directly without the person
signing up themselves.

---

## Running it

**Streamlit app (primary interface — Scanner + Dashboard, login-gated):**

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

**REST API (optional, for integrating into your own app):**

```bash
uvicorn api:app --reload --port 8000
```

Shares the exact same accounts as the Streamlit app — register a new
one or log in with an existing one, either way getting an access token
(short-lived) and a refresh token (longer-lived) back:

```bash
# new account:
RESP=$(curl -s -X POST http://localhost:8000/register -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","first_name":"Your","last_name":"Name","password":"SecurePass1!","password_confirm":"SecurePass1!"}')

# or an existing one:
RESP=$(curl -s -X POST http://localhost:8000/login \
  -F "username=you@example.com" -F "password=<your password>")

TOKEN=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
REFRESH=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")

curl -X POST http://localhost:8000/scan \
  -H "Authorization: Bearer $TOKEN" -F "file=@photo.jpg"
```

When the access token expires, trade the refresh token for a new one
instead of sending the password again:

```bash
NEW_TOKEN=$(curl -s -X POST http://localhost:8000/refresh \
  -H "Content-Type: application/json" -d "{\"refresh_token\": \"$REFRESH\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

### Deploy the browser app to Vercel

The Vercel deployment serves a browser-based interface from `public/` and
runs the existing FastAPI endpoints through Vercel's Python runtime. The
Streamlit interface remains available for local use; both interfaces use
the same scanner and privacy engines.

1. Create a Neon PostgreSQL database and copy its pooled connection string.
2. Import this GitHub repository into Vercel. No framework override or build
   command is needed; `pyproject.toml` selects `api:app`.
3. Add `DATABASE_URL` to the Vercel project's Production, Preview, and
   Development environment variables, then redeploy. The app creates its
   PostgreSQL tables automatically.
4. Open the Vercel deployment URL and create an account.

Vercel's filesystem is ephemeral, so `DATABASE_URL` is required there.
Account password hashes, the API signing key, consent registry, pattern
history, and scan summary history are stored in PostgreSQL. Uploaded images
are processed by the API and are not written to those tables. The hosted
deployment does receive images submitted for scanning; deploy only if you
trust the hosting account and review its data-retention and access settings.

**OCR note:** the Python OCR integration requires the Tesseract executable.
Vercel's standard Python runtime does not install that system binary, so the
browser interface explicitly reports OCR errors when it cannot run. Other
scan, redaction, consent, history, pattern, camera-evaluation, and vault
features remain available. For OCR on Vercel, use a runtime that includes
Tesseract or configure a separately managed OCR service.

Camera access requires HTTPS (Vercel deployments use HTTPS). The viewfinder
does not continuously upload video: a still frame is sent only after the
operator selects **Evaluate frame**.

- `POST /register` — email/name/password → same response shape as
  `/login` (creates the account and logs it in immediately). Email
  doubles as the username. Same password policy as the Streamlit
  sign-up form (8–20 characters, upper + lower case, a digit, a special
  character) — enforced by the same library call, not a second
  implementation that could drift. No captcha here — see Accounts &
  Dashboard for why, and what to add yourself if you expose this
  publicly.
- `POST /login` — username + password →
  `{"access_token", "refresh_token", "token_type"}`. Access tokens
  expire after `token_expiry_minutes` (default 60); refresh tokens
  after `refresh_token_expiry_days` (default 30) — both configurable
  in `auth_config.yaml`.
- `POST /refresh` — a still-valid refresh token → a new
  `{"access_token", "token_type"}`. The two token types are checked,
  not just trusted by name: an access token can't be used at
  `/refresh`, and a refresh token can't be used at `/scan` or
  `/redact` — each is rejected the same way an expired or garbage
  token would be, so the error itself doesn't reveal which was wrong.
- `POST /scan` — upload an image, get the full JSON risk report back
- `POST /redact` — upload an image, get the blurred JPEG back directly
  (with `X-Risk-Score` / `X-Risk-Level` response headers)
- `GET /health` — no auth required, for uptime checks
- Interactive docs at `http://localhost:8000/docs` — the "Authorize"
  button there accepts a username/password and handles the access
  token for you, so you can try `/scan` and `/redact` straight from
  the browser. `/refresh` isn't part of that flow; call it directly.
- Every `/scan` and `/redact` call is logged to the same scan history
  as the Streamlit app (see Accounts & Dashboard) — one unified history
  regardless of which surface you used.
- Both token types are stateless JWTs, signed with their own secret
  (`auth_config.yaml`'s `api` section) independent from the Streamlit
  app's cookie key — rotating one doesn't log you out of the other.
  Nothing about an individual token is tracked server-side, so there's
  no way to revoke just one early: `regenerate-api-key` invalidates
  every outstanding access *and* refresh token at once (they share the
  signing key), and that's the only revocation lever — by design, not
  by oversight. See Accounts & Dashboard.

**Tests (no real photos needed — generates a synthetic test image):**

```bash
python3 tests/test_pipeline.py
```

**Demo (see detection + redaction run against a live scene, with images):**

```bash
python3 demo/generate_demo.py
```

Outputs land in `demo/output/` — see `demo/README.md` for what each one
shows and what's live detection vs. illustrated.

---

## Accounts & Dashboard

The app is login-gated (`streamlit-authenticator`, bcrypt-hashed
passwords, signed cookie for session persistence), and the REST API
(`api.py`) shares the exact same accounts via its own bearer-token
login — one set of users, works on both surfaces.

**Anyone who can reach the app can create their own account** — a
"Sign up" tab next to "Log in" (and a matching `POST /register` on the
API), like Google/Gmail: your email is your username, no separate one
to remember. This is a deliberate change from a purely invite-only
model — the tradeoff is real, so it's worth being explicit about it:
open registration means access control now rests entirely on *who can
reach the app* (your network/firewall, not this project) rather than
on *who you've personally added*. Fine for a home network or a small
team behind your own auth/VPN; think it through before putting either
surface on the open internet. If you want the old invite-only model
back, it's one code change — skip rendering the "Sign up" tab in
`app.py` and the `/register` route in `api.py`, and go back to
`manage_users.py add` as the only way in.

Passwords must be 8–20 characters with at least one uppercase letter,
one lowercase letter, one digit, and one special character — enforced
by the same library call on both the Streamlit form and `/register`,
not two separate implementations that could quietly drift apart.
Sign-up on the Streamlit app also requires solving an inline image
captcha (basic bot resistance); `/register` doesn't, since a captcha is
an image a human reads and that doesn't translate to a script-driven
API — if you expose `/register` beyond your own machine, put your own
rate-limiting or bot-prevention in front of it.

**No self-service "forgot password."** The underlying library has one,
but it either emails the new password (routes your users' email
addresses through a third-party hosted service, which doesn't sit well
for a privacy tool) or — with no email step at all — hands the new
password to whoever typed in a username, no proof they own the account
required. That's a real account-takeover path, not a hypothetical one,
so it's not wired up. Password resets go through
`manage_users.py set-password <username>` — an admin action, same as
before self-registration existed. If you want self-service resets
badly enough to configure real email delivery yourself, see Possible
extensions.

Beyond registration, `manage_users.py` is still how you manage
accounts directly (handy for removing someone, or fixing an account
without their involvement):

```bash
python3 scripts/manage_users.py add <username> "<Full Name>" <email>
python3 scripts/manage_users.py set-password <username>
python3 scripts/manage_users.py remove <username>
python3 scripts/manage_users.py list
python3 scripts/manage_users.py regenerate-cookie-key   # Streamlit sessions
python3 scripts/manage_users.py regenerate-api-key       # REST API tokens
```

There are no shipped accounts or credentials. The auth config is
created when the first account is added and stays local; keep it
gitignored so password hashes and the API signing key are not published.

Credentials live in `auth_config.yaml` (bcrypt hashes and signing keys,
never plaintext passwords). It's gitignored by default — if you fork
this into your own repo, keep it that way, or your password hashes and
both signing keys end up public too. Opening an older copy of this
project's `auth_config.yaml`? `manage_users.py` and `api.py` both
auto-add a missing `api` section (with a fresh, random key) the first
time they touch a config file that predates REST API auth — nothing
manual required.

**Dashboard page:** every scan — from the Scanner page *or* the REST
API — is logged locally to `data/scan_history.db` (SQLite) — timestamp,
filename, risk score/level, and finding counts only. **Never the image
itself, never OCR text or any extracted content** — a "privacy tool"
whose own history log became a privacy risk would defeat the point.
Each user sees only their own history; there's no cross-user view in
the UI by design. Deployed for more than a few trusted people and want
an admin overview? Query the SQLite file directly rather than adding a
UI toggle for it — that keeps "who can see whose scan history" an
explicit, deliberate choice rather than a checkbox someone flips by
accident.

This auth setup — cookies for the Streamlit app, bearer tokens for the
API — is appropriately lightweight for local or trusted small-group
use. If you deploy either surface on the open internet, put it behind
HTTPS at minimum: JWTs and session cookies are both just as
interceptable as a plaintext password if the connection itself isn't
encrypted. Treat both as lightweight session systems, not a substitute
for a real identity provider if that's what the deployment needs.

---

## How redaction works

`modules/image_utils.py` handles blurring/pixelating detected regions.
Three things matter more than which filter you pick:

1. **Safety padding.** Detector boxes are never pixel-perfect — a
   slightly-short box leaves a sliver of the real content exposed. Every
   region is expanded outward (15% by default, adjustable in the
   dashboard) before redacting.
2. **Adaptive strength.** Blur/pixelation strength scales with the
   region's own size. This isn't just cosmetic — while building this,
   the old fixed-strength version left eyes and mouth faintly visible as
   darker patches on a large face-sized region, because one fixed kernel
   size doesn't cover every region size well. See
   `demo/output/05_face_blur_quality.jpg` and
   `test_redaction_strength_scales_with_region_size` in the test suite.
3. **Feathered edges.** The transition at the outer edge is a smooth
   gradient instead of a hard rectangular cut — verified in
   `tests/test_pipeline.py` to spread over ~13 pixels instead of 1. The
   core detection + padding is always fully redacted first; feathering
   only softens the *added margin*, never the sensitive content itself.
4. **Elliptical shaping for faces.** `apply_redactions` feathers faces
   to a natural oval instead of a rectangle — never less coverage than
   the rectangle (the ellipse circumscribes the padded box with margin,
   corners included), just a cosmetic edge that suits a round region.
   One real limitation found while building this, not a hypothetical:
   the ellipse only *looks* oval blended against continuous content.
   Pixelation is a coarse average of the whole region, and a block that
   lands entirely on flat background pixelates back to that same flat
   value — with nothing visibly different to blend toward, no alpha
   shape can show through, and the visible edge degrades toward the
   content's own rectangular footprint instead (confirmed by directly
   inspecting the output, not assumed). So faces specifically get
   `gaussian` instead of `auto`/`pixelate`, regardless of which method
   you picked for everything else — proven to render the oval cleanly,
   and still a genuinely strong redaction at the adaptive strength this
   module already uses. See `demo/output/05_face_blur_quality.jpg` and
   `modules/image_utils.py`'s module docstring for the full story,
   including the corner-softening bug this same investigation found and
   fixed (a Gaussian-blurred mask fades its own corners faster than its
   edge midpoints — the true content's corners were measurably less
   covered than its edges until the shape is re-asserted at full
   strength after the blur, not just drawn once beforehand).

`method="auto"` (the default) pixelates strongly, then applies a light
blur on top — pixelation destroys detail more thoroughly than blur alone
at equivalent visual strength, and the light blur softens the blockiness
so it reads as intentional. `gaussian`, `pixelate`, and `solid` are also
available; `solid` is the strongest option and the right call for
content you never want reconstructed (a document, or a high-stakes
child-safety case) rather than relying on blur alone.

**Honesty check:** no blur or pixelation is *provably* irreversible
against a sufficiently sophisticated attacker — there's published
research on reconstructing blurred/pixelated faces. Treat redaction as
raising the bar significantly, not as a mathematical guarantee.

See `demo/` for a full run of this against a live-detected scene,
including an old-vs-new zoomed comparison.

## How the risk score works

Every finding adds weighted points (see `WEIGHTS` in
`modules/risk_analyzer.py`), capped at 100:

| Finding | Points |
|---|---|
| Possible minor detected | 35 (highest — child safety is weighted deliberately heavy) |
| SSN-like / credit-card-like number | 35 |
| ID document keyword (e.g. "passport", "driver's license") | 30 |
| GPS location in metadata | 25 |
| License plate | 20 |
| Passport-number-shaped text | 20 |
| Face | 15 |
| Phone number | 10 |
| Email address | 8 |
| Background object (screen, document, bystander) | 5 |

`0–20` Low · `21–50` Medium · `51–75` High · `76–100` Critical

These weights encode a judgment call, not a scientific model — open
`modules/risk_analyzer.py` and adjust `WEIGHTS`/thresholds to match your
own risk tolerance.

---

## ⚠️ Limitations & responsible use — please read

- **Not facial recognition.** This never tries to determine *who*
  someone is — only whether a face/plate/document is present.
- **Age estimation will sometimes be wrong, in both directions.** The
  Child Safety Detector is tuned to over-flag rather than under-flag
  (a false "please double check" costs a click; a missed minor costs
  real risk). Regardless of what it says, look at any photo with
  children in it yourself before posting.
- **OCR and regex matching are heuristic.** They'll miss things, and
  occasionally flag harmless text. Use findings as a prompt to look
  closer, not as a certainty.
- **Run it locally.** This project processes images entirely on your
  own machine — nothing is uploaded to a third party by this code. If
  you deploy the API somewhere, keep that property in mind; piping
  photos through an untrusted hosted version of this tool would defeat
  the point.
- **This reduces risk, it doesn't eliminate it.** A single image is
  only one channel of exposure. Determined, targeted harassment can
  combine information from multiple sources beyond one photo. Treat
  this as one layer of a broader personal-safety practice.

---

## Project structure

```
ai-privacy-scanner/
├── app.py                        # Entry point: login gate + navigation + logout
├── api.py                        # Optional FastAPI REST API (own bearer-token login, same accounts)
├── auth_config.yaml              # Login credentials (bcrypt-hashed) + cookie config
├── requirements.txt
├── ui/
│   ├── scanner_page.py           # Upload -> scan -> risk -> redact -> safe post (logs to history)
│   └── dashboard_page.py         # Your scan history: totals, chart, recent-scans table
├── modules/
│   ├── detection_module.py       # Face (Haar, auto-upgrades to DNN) + plate + optional YOLO
│   ├── ocr_extractor.py          # OCR + sensitive-text pattern matching
│   ├── child_safety_detector.py  # Age-bracket flagging (optional model, safe fallback)
│   ├── metadata_scanner.py       # EXIF/GPS scan + strip
│   ├── risk_analyzer.py          # Weighted risk scoring engine
│   ├── image_utils.py            # Blur / pixelate / draw-box helpers (padding, feathering, adaptive strength)
│   ├── scan_history.py           # SQLite scan log (metadata only, never the image)
│   ├── api_auth.py                # JWT bearer-token auth for api.py, shares auth_config.yaml
│   └── scanner.py                # Orchestrator ("AI Scanner")
├── scripts/
│   ├── download_models.py        # Fetches optional DNN face + age models (tested, working URLs)
│   └── manage_users.py           # Add/remove users, set passwords, regenerate the cookie key
├── demo/
│   ├── generate_demo.py          # Builds a live-detected scene + old-vs-new redaction comparison
│   └── output/                   # Generated images (regenerate anytime, nothing bundled)
├── tests/
│   └── test_pipeline.py          # End-to-end smoke tests + redaction-quality checks
├── data/                         # scan_history.db lands here (gitignored, created on first scan)
├── models/                       # Optional downloaded model weights land here
└── sample_images/                # Drop your own test photos here (none bundled)
```

## Possible extensions

- Add a proper trained plate detector instead of the Haar
  cascade + contour fallback for non-Russian plate formats.
- Hook `/redact`'s output into an actual posting flow (Instagram/X/etc.
  APIs) once you've decided how you want to handle auth for that.
- Batch-mode CLI for scanning a whole folder before a bulk upload.
- Swap the rule-based Risk Analyzer for a trained/calibrated model once
  you have labeled examples of what your users consider risky.
- Self-registered accounts backed by a real database instead of the
  YAML-file credentials store (see Accounts & Dashboard) if open
  sign-up grows past what a flat file comfortably handles, or if you
  need concurrent registrations to be fully race-safe.
- Self-service "forgot password" with real email delivery, if you're
  willing to configure SMTP/a transactional-email provider yourself —
  see Accounts & Dashboard for why it's not wired up by default.
- Email verification on sign-up (confirm the address before the
  account is usable) — same email-infrastructure tradeoff as forgot
  password, and the same reason it's not there by default.
- A revocation list (or move to a DB-backed session store) for the
  REST API's tokens, if "rotate the key and force everyone to log in
  again" is too blunt an instrument for revoking a single compromised
  token — see the tradeoff noted under REST API above.
