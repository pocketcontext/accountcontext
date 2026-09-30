// Format authoritative integer minor units without floating point division.
export function money(
  value: number,
  currency: unknown,
  exponent: unknown,
): string {
  const scale = Number(exponent);
  const allowed: Record<string, number> = {
    USD: 2,
    EUR: 2,
    GBP: 2,
    CHF: 2,
    CAD: 2,
    AUD: 2,
    INR: 2,
    JPY: 0,
    KWD: 3,
  };
  if (
    !Number.isSafeInteger(value) ||
    value < 0 ||
    typeof currency !== "string" ||
    allowed[currency] !== scale
  )
    return `${value} minor units${typeof currency === "string" && currency ? " · " + currency : ""}`;
  const digits = String(value).padStart(scale + 1, "0");
  return `${currency} ${scale ? digits.slice(0, -scale) + "." + digits.slice(-scale) : digits}`;
}
