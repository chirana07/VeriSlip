# Upload security review

This document records the repository-wide upload review performed for issue
#92. It distinguishes controls that were already present from the additional
hardening introduced by that issue.

## Reviewed attack surface

The review covered public verification, background-job, batch, live-scanner,
WooCommerce, courier, WhatsApp, and signed Shopify ingestion paths. It also
reviewed OCR temporary files, PDF rendering, dataset tools, and archive use.
The public API has no archive-upload endpoint.

The primary threats considered were path traversal and hostile filenames,
content-type spoofing, SVG active content, malformed images, decompression
bombs, oversized request bodies, unsafe temporary files, unbounded PDF
rendering, and disclosure of paths or document data in errors and logs.

## Protections that already existed

- Public image paths use `core.security.image_sanitizer`, which identifies
  encoded content instead of trusting the filename or client Content-Type.
- Only decodable JPEG and PNG images are accepted. SVG, animated images,
  malformed/truncated input, and other formats are rejected.
- Encoded images are limited to 10 MiB, dimensions to 6000 by 6000 pixels, and
  total pixels to 20 million. Pillow decompression-bomb warnings and errors
  fail closed.
- Accepted images are fully decoded, converted to detached RGB pixels, and
  have source metadata removed before forensic processing.
- PDF input is byte-bounded, limited to the first page, and dimension-checked
  before rendering. Native document and page handles are closed.
- WhatsApp and Shopify downloads use timeouts, HTTPS host restrictions,
  streaming byte limits, media-type allowlists, and the shared image sanitizer.
- Courier and WhatsApp base64 payloads have encoded-size limits and are passed
  through the shared sanitizer after decoding.
- The OCR bridge uses a securely generated temporary filename and removes it
  in a `finally` block. No reviewed upload route used the client filename as a
  filesystem destination.
- Dataset manifest verification rejects absolute, traversing, and symlinked
  paths. It is a read-only offline workflow rather than a public upload path.

## Gaps fixed by issue #92

Route handlers previously enforced per-file limits only after Starlette had
parsed the multipart or JSON request. A centralized ASGI middleware now caps
the entire request envelope before parsing. It checks both `Content-Length`
and bytes actually received, so omitted or understated length headers do not
bypass the limit. Route-level decoder limits remain the authoritative per-file
checks.

Batch responses previously returned the untrusted multipart filename and the
web UI inserted that value into HTML. The API now returns generated labels such
as `upload_001`; it does not reflect path-like, control-character, Unicode, or
oversized client filenames. The UI also assigns the label with `textContent`.
Uploaded spool files are explicitly closed immediately after the bounded read.

## Formats and limits

| Ingestion path | Accepted document content | Request envelope limit |
| --- | --- | --- |
| Verify, job, live, WooCommerce | JPEG, PNG; verify/WooCommerce also bounded PDF | 10 MiB plus 1 MiB framing |
| Batch verification | Up to 25 JPEG/PNG/PDF items | 25 x 10 MiB plus 1 MiB framing |
| Courier and WhatsApp JSON | Base64 JPEG/PNG | Base64 expansion of 10 MiB plus 256 KiB JSON framing |
| Shopify webhook | Signed JSON; downloaded JPEG/PNG proof | 1,000,000-byte webhook body; remote image capped at 10 MiB |

SVG is intentionally unsupported. Renaming SVG or sending it as `image/png`
does not make it valid because decoded content is checked. GIF, WebP, animated
images, corrupt images, truncated files, oversized images, and detected
decompression bombs are likewise rejected.

## Path and temporary-file policy

Client filenames are display metadata only and must not form local paths.
Current batch handling replaces them with server-generated labels. New code
that must persist an upload should generate its own opaque identifier, confine
the resolved destination to an application-owned directory, and use secure
temporary-file APIs. In-memory processing is preferred for sensitive receipts.

Upload errors are deliberately generic. They must not contain source bytes,
client filenames, filesystem paths, decoder internals, credentials, or stack
traces. Structured request logs record route and correlation metadata, not
request bodies.

## Guidance for new ingestion endpoints

1. Add the exact route and a conservative envelope cap to
   `UPLOAD_BODY_LIMITS`.
2. Bound streamed or base64 input before decoding.
3. Pass decoded images through `sanitize_image_bytes`; do not create a second
   image validator or trust extensions and MIME headers.
4. Reject SVG rather than attempting regex-based sanitization.
5. Never use a supplied filename as a storage destination or return it in HTML.
6. Bound PDF pages and rendered dimensions before expensive work.
7. Mock remote services and add malformed, oversized, spoofed-type, and safe
   normal-image regression tests.

## Remaining limitations

The application-level request cap is defense in depth; deployments should also
configure equivalent or smaller limits in the reverse proxy and application
server. Multipart parsing may spool data within the bounded envelope, although
spools are now closed promptly. The repository contains archive extraction in
a generated training notebook, but no externally reachable archive ingestion;
trusted research archives still require operator care. The sanitizer validates
file structure and resource bounds, not every possible decoder-library flaw,
so Pillow and PDF dependencies should remain patched.

