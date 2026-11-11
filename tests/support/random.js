// Seeded random numbers, so a failed run can be repeated with the same products.
// playwright.config.js sets E2E_SEED once per run when it is not given.
export const seed = Number(process.env.E2E_SEED);

// mulberry32: small and repeatable, fine for picking test data (not for security)
export function createRandom(startSeed = seed) {
  let state = startSeed >>> 0;
  const next = () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return {
    next,
    // Whole number from min to max, both included
    int: (min, max) => min + Math.floor(next() * (max - min + 1)),
    pick: (items) => items[Math.floor(next() * items.length)],
    // `count` different items in random order (Fisher–Yates on a copy)
    sample(items, count) {
      const copy = [...items];
      for (let i = copy.length - 1; i > 0; i--) {
        const j = Math.floor(next() * (i + 1));
        [copy[i], copy[j]] = [copy[j], copy[i]];
      }
      return copy.slice(0, count);
    },
  };
}