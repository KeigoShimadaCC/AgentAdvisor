/**
 * Number formatting helpers shared across screens.
 *
 * Kept out of ``terms.ts`` because that module is the terminology lexicon —
 * these are presentation rules, not wording.
 */

/**
 * Format a modeled expected value for display.
 *
 * Expected values are monetary in the investment vertical, so a bare ``11000``
 * reads as an unlabeled magnitude. We render grouped digits with a currency
 * symbol and no cents — EVs are scenario-model outputs, and trailing cents
 * would imply a precision the model does not have.
 *
 * Falls back to a plain grouped number when no currency is known.
 */
export function formatExpectedValue(
  value: number,
  currency: string | null | undefined = "USD",
): string {
  if (!Number.isFinite(value)) return "—";
  try {
    if (currency) {
      return new Intl.NumberFormat(undefined, {
        style: "currency",
        currency,
        maximumFractionDigits: 0,
      }).format(value);
    }
  } catch {
    // Unknown currency code — fall through to the plain grouped form.
  }
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value);
}
