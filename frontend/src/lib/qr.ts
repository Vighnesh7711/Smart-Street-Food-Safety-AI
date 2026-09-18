/**
 * Parsing the text a QR scan produces.
 *
 * Deliberately a pure module with no React and no browser APIs: this is the
 * single piece of client logic that decides **which stall a consumer is
 * shown**, so it is the one frontend function worth unit-testing. A sloppy
 * regex here is a wrong-stall bug.
 */

/** Matches a stall code anywhere in a path: /stall/AB12CD34EF */
const STALL_PATH_PATTERN = /\/stall\/([0-9A-Za-z]+)/;

/** A bare code on its own, with surrounding whitespace tolerated. */
const BARE_CODE_PATTERN = /^[0-9A-Za-z]{4,16}$/;

/** The QR alphabet: Crockford-style, no I/L/O/U. */
const CODE_ALPHABET = /^[0-9ABCDEFGHJKMNPQRSTVWXYZ]{4,16}$/;

/**
 * Extract a stall code from scanned text.
 *
 * Three real inputs are handled:
 *   1. The full URL our own QR encodes — `https://host/stall/AB12CD34EF`.
 *      This is the common case: the stickers encode a URL so a consumer's
 *      ordinary camera app opens them.
 *   2. A bare code, for a sticker printed by an older or custom generator.
 *   3. Anything else — a link to another site, a WiFi QR, a phone number —
 *      which must be **rejected** rather than coerced into a lookup.
 *
 * Returns the code in canonical (uppercase) form, or null if the text is not
 * a stall code. Callers show "that is not a stall QR code" on null; they must
 * never navigate with a guessed value.
 */
export function stallCodeFromScan(raw: string | null | undefined): string | null {
  if (!raw) return null;

  const text = raw.trim();
  if (!text) return null;

  // 1. A URL containing /stall/<code>, on any host. Matching on the path
  //    rather than an exact origin means a sticker printed against a staging
  //    or renamed domain still resolves.
  const pathMatch = text.match(STALL_PATH_PATTERN);
  if (pathMatch) {
    const candidate = pathMatch[1].toUpperCase();
    // Reject look-alike characters: our generator never emits I, L, O or U,
    // so a code containing one came from somewhere else.
    return CODE_ALPHABET.test(candidate) ? candidate : null;
  }

  // 2. A bare code.
  if (BARE_CODE_PATTERN.test(text)) {
    const candidate = text.toUpperCase();
    return CODE_ALPHABET.test(candidate) ? candidate : null;
  }

  // 3. Anything else. Notably this rejects a URL to a different site even if
  //    it happens to contain a code-like segment elsewhere in the path.
  return null;
}

/**
 * Human-readable reason a scan was rejected, for the scanner UI.
 *
 * Split from the parser so the parser stays a pure predicate and the wording
 * lives in one place.
 */
export function describeScanRejection(raw: string | null | undefined): string {
  const text = (raw ?? "").trim();
  if (!text) return "Nothing was detected. Hold the code steady in the frame.";
  if (/^https?:\/\//i.test(text)) {
    return "That QR code is for a different website, not a stall.";
  }

  // Plausible shape, rejected only by the alphabet. Most often this is a
  // mistyped code -- our alphabet drops the characters that look like
  // digits, so saying which ones helps more than "invalid".
  const candidate = text.match(STALL_PATH_PATTERN)?.[1] ?? text;
  if (
    BARE_CODE_PATTERN.test(candidate) &&
    !CODE_ALPHABET.test(candidate.toUpperCase())
  ) {
    return "Stall codes never contain the letters I, L, O or U. Please check the code and try again.";
  }

  return "That does not look like a stall QR code.";
}
