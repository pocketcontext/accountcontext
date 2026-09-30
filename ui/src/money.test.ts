import { it, expect } from "vitest";
import { money } from "./money";
it("preserves every minor unit and uses only authoritative currency exponents", () => {
  expect(money(9007199254740991, "USD", 2)).toBe("USD 90071992547409.91");
  expect(money(1, "KWD", 3)).toBe("KWD 0.001");
  expect(money(123, "JPY", 0)).toBe("JPY 123");
  expect(money(123, "USD", 0)).toBe("123 minor units · USD");
  expect(money(123, "ZZZ", 2)).toBe("123 minor units · ZZZ");
});
