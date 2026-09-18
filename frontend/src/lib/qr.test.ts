import { describe, expect, it } from "vitest";

import { describeScanRejection, stallCodeFromScan } from "./qr";

/**
 * These matter more than their size suggests.
 *
 * `stallCodeFromScan` is the one piece of client logic that decides which
 * stall a consumer is shown after scanning. Getting it wrong sends someone
 * to a different stall's hygiene record while they are standing in front of
 * this one -- so the rejection cases are as important as the acceptance
 * cases.
 */

const VALID = "AB12CD34EF";

describe("stallCodeFromScan — accepted inputs", () => {
  it("extracts the code from a full URL", () => {
    expect(stallCodeFromScan(`https://food.example.com/stall/${VALID}`)).toBe(VALID);
  });

  it("works over http and with a port", () => {
    expect(stallCodeFromScan(`http://localhost:3000/stall/${VALID}`)).toBe(VALID);
  });

  it("works on any host", () => {
    // A sticker printed against a renamed or staging domain must still
    // resolve; matching the path rather than an exact origin is what makes
    // that true.
    expect(stallCodeFromScan(`https://staging.internal.test/stall/${VALID}`)).toBe(
      VALID
    );
  });

  it("tolerates a trailing slash and query string", () => {
    expect(stallCodeFromScan(`https://x.test/stall/${VALID}/`)).toBe(VALID);
    expect(stallCodeFromScan(`https://x.test/stall/${VALID}?src=qr`)).toBe(VALID);
  });

  it("accepts a bare code", () => {
    expect(stallCodeFromScan(VALID)).toBe(VALID);
  });

  it("uppercases a lowercase code", () => {
    // The alphabet is uppercase, so uppercasing is lossless and lets a
    // hand-typed code work.
    expect(stallCodeFromScan(VALID.toLowerCase())).toBe(VALID);
    expect(stallCodeFromScan(`https://x.test/stall/${VALID.toLowerCase()}`)).toBe(
      VALID
    );
  });

  it("trims surrounding whitespace", () => {
    expect(stallCodeFromScan(`  ${VALID}  `)).toBe(VALID);
  });

  it("accepts every character of the alphabet", () => {
    // Crockford-style: no I, L, O or U. These are the letters that appear in
    // the alphabet but not in hex, so a hex-only pattern would wrongly
    // reject them.
    expect(stallCodeFromScan("GHJKMNPQRS")).toBe("GHJKMNPQRS");
    expect(stallCodeFromScan("TVWXYZ0123")).toBe("TVWXYZ0123");
    expect(stallCodeFromScan("9ABCDEFGHJ")).toBe("9ABCDEFGHJ");
  });
});

describe("stallCodeFromScan — rejections", () => {
  it("rejects unrelated URLs", () => {
    // Must not navigate: this would otherwise be coerced into a lookup.
    expect(stallCodeFromScan("https://example.com")).toBeNull();
    expect(stallCodeFromScan("https://example.com/products/12345")).toBeNull();
  });

  it("rejects a URL that merely contains the word stall", () => {
    expect(stallCodeFromScan("https://example.com/stallions/ABC123")).toBeNull();
  });

  it("rejects non-QR payloads", () => {
    expect(stallCodeFromScan("WIFI:S:MyNetwork;T:WPA;P:secret;;")).toBeNull();
    expect(stallCodeFromScan("tel:+919876543210")).toBeNull();
    expect(stallCodeFromScan("mailto:someone@example.com")).toBeNull();
    expect(stallCodeFromScan("BEGIN:VCARD\nFN:Someone")).toBeNull();
  });

  it("rejects codes containing look-alike characters", () => {
    // Our generator never emits I, L, O or U, so a code with one came from
    // somewhere else and must not be looked up.
    expect(stallCodeFromScan("AB12CD34EI")).toBeNull();
    expect(stallCodeFromScan("AB12CD34EL")).toBeNull();
    expect(stallCodeFromScan("AB12CD34EO")).toBeNull();
    expect(stallCodeFromScan("AB12CD34EU")).toBeNull();
  });

  it("rejects empty and whitespace-only input", () => {
    expect(stallCodeFromScan("")).toBeNull();
    expect(stallCodeFromScan("   ")).toBeNull();
    expect(stallCodeFromScan(null)).toBeNull();
    expect(stallCodeFromScan(undefined)).toBeNull();
  });

  it("rejects codes that are too short or too long", () => {
    expect(stallCodeFromScan("AB")).toBeNull();
    expect(stallCodeFromScan("A".repeat(40))).toBeNull();
  });

  it("rejects free text", () => {
    expect(stallCodeFromScan("hello world")).toBeNull();
    expect(stallCodeFromScan("Ramesh Vada Pav")).toBeNull();
  });
});

describe("describeScanRejection", () => {
  it("explains an empty scan", () => {
    expect(describeScanRejection("")).toMatch(/hold the code steady/i);
  });

  it("explains a foreign URL", () => {
    expect(describeScanRejection("https://example.com/x")).toMatch(
      /different website/i
    );
  });

  it("names the forbidden characters for a plausible mistyped code", () => {
    // "I" is not in the alphabet; telling the user which characters cannot
    // appear is more useful than "invalid".
    expect(describeScanRejection("AB12CD34EI")).toMatch(/I, L, O or U/);
  });

  it("falls back to a generic message", () => {
    expect(describeScanRejection("some random text")).toMatch(
      /does not look like/i
    );
  });
});
