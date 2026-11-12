// Selectors for the mobile bottom bar and its search dialog
// (shop/themes/ciocia/templates/_partials/bottom-nav.tpl, issue #32).
export class BottomNav {
  constructor(page) {
    this.page = page;
    this.nav = page.getByRole("navigation", { name: "Skróty" });
    this.items = this.nav.locator(".ciocia-bottom-nav__item");
    this.categories = this.nav.getByRole("button", { name: "Kategorie" });
    this.search = this.nav.getByRole("button", { name: "Szukaj" });
    this.cart = this.nav.getByRole("link", { name: /^Koszyk/ });
    this.cartBadge = this.nav.locator(".ciocia-bottom-nav__badge");
    this.drawer = page.locator("#mobile_top_menu_wrapper");
    this.searchDialog = page.locator("#ciocia-search-dialog");
    this.searchInput = this.searchDialog.getByRole("searchbox", { name: "Nazwa produktu" });
  }
}
