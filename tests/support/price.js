// Prices as the shop prints them ("1 234,56 zł", with a non-breaking space) to grosze, so sums are exact.
// Returns null for a text with no amount, such as "Za darmo!".
export function toGrosze(text) {
  const amount = text.replace(/[^\d,]/g, "");
  if (!amount) return null;
  const [zloty, grosze = "0"] = amount.split(",");
  return Number(zloty) * 100 + Number(grosze.padEnd(2, "0"));
}
