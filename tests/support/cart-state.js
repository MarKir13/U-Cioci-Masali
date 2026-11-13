// Cart contents as the shop sees them, read from PrestaShop's front-end object on the current page.
// Sorted, so two snapshots can be compared with toEqual whatever order the shop lists them in.
export async function cartSnapshot(page) {
  const lines = await page.evaluate(() =>
    globalThis.prestashop.cart.products.map((product) => ({
      id: `${product.id_product}-${product.id_product_attribute}`,
      name: product.name,
      quantity: Number(product.quantity),
    })),
  );
  return lines.sort((a, b) => a.id.localeCompare(b.id));
}
