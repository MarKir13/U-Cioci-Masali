{**
 * Mobile bottom navigation, as on the source shop: five shortcuts fixed to the bottom of the window
 * below 768 px (hidden-md-up), plus the search dialog opened by "Szukaj".
 * Included from _partials/footer.tpl, but not on checkout, where the source shop has no bar.
 * custom.js opens the category drawer and the search dialog and keeps the cart count up to date.
 *}
{assign var='ciocia_page_name' value=$page.page_name}
{assign var='ciocia_cart_count' value=$cart.products_count|intval}

{* Keeps the end of the page (footer copyright) visible above the fixed bar. *}
<div class="ciocia-bottom-nav-spacer hidden-md-up" aria-hidden="true"></div>

<nav class="ciocia-bottom-nav hidden-md-up" aria-label="Skróty">
  <button type="button" class="ciocia-bottom-nav__item" data-bottom-nav-categories
    aria-controls="mobile_top_menu_wrapper" aria-expanded="false">
    <i class="material-icons" aria-hidden="true">view_list</i>
    <span class="ciocia-bottom-nav__label">Kategorie</span>
  </button>

  <a class="ciocia-bottom-nav__item"
    href="{$link->getModuleLink('blockwishlist', 'lists')|escape:'htmlall':'UTF-8'}"
    {if $ciocia_page_name == 'module-blockwishlist-lists'}aria-current="page"{/if}>
    <i class="material-icons" aria-hidden="true">favorite_border</i>
    <span class="ciocia-bottom-nav__label">Ulubione</span>
  </a>

  <button type="button" class="ciocia-bottom-nav__item ciocia-bottom-nav__item--search" data-bottom-nav-search
    aria-controls="ciocia-search-dialog" aria-haspopup="dialog">
    <span class="ciocia-bottom-nav__search-circle" aria-hidden="true">
      <i class="material-icons">search</i>
    </span>
    <span class="ciocia-bottom-nav__label">Szukaj</span>
  </button>

  <a class="ciocia-bottom-nav__item" rel="nofollow" href="{$urls.pages.cart|escape:'htmlall':'UTF-8'}"
    {if $ciocia_page_name == 'cart'}aria-current="page"{/if}>
    <span class="ciocia-bottom-nav__icon">
      <i class="material-icons" aria-hidden="true">shopping_cart</i>
      <span class="ciocia-bottom-nav__badge" aria-hidden="true" data-cart-count
        {if $ciocia_cart_count == 0}hidden{/if}>{$ciocia_cart_count}</span>
    </span>
    <span class="ciocia-bottom-nav__label">Koszyk</span>
    <span class="sr-only">, produkty: <span data-cart-count>{$ciocia_cart_count}</span></span>
  </a>

  <a class="ciocia-bottom-nav__item" rel="nofollow" href="{$urls.pages.my_account|escape:'htmlall':'UTF-8'}"
    {if $ciocia_page_name == 'my-account'}aria-current="page"{/if}>
    <i class="material-icons" aria-hidden="true">account_circle</i>
    <span class="ciocia-bottom-nav__label">Konto</span>
  </a>
</nav>

<dialog id="ciocia-search-dialog" class="ciocia-search-dialog" aria-labelledby="ciocia-search-dialog-title">
  <div class="ciocia-search-dialog__head">
    <h2 id="ciocia-search-dialog-title" class="ciocia-search-dialog__title">Czego szukasz?</h2>
    {* method="dialog" closes the dialog without JS; the browser returns focus to the opener. *}
    <form method="dialog">
      <button type="submit" class="ciocia-search-dialog__close" aria-label="Zamknij wyszukiwanie">
        <i class="material-icons" aria-hidden="true">close</i>
      </button>
    </form>
  </div>
  {* Same request as the header search (ps_searchbar): GET to the search page with "s". *}
  <form class="ciocia-search-dialog__form" method="get" action="{$urls.pages.search|escape:'htmlall':'UTF-8'}" role="search">
    <input type="hidden" name="controller" value="search">
    <label class="sr-only" for="ciocia-search-dialog-input">Nazwa produktu</label>
    <input id="ciocia-search-dialog-input" class="ciocia-search-dialog__input" type="search" name="s"
      placeholder="Wpisz nazwę produktu…" minlength="3" required enterkeyhint="search" autocomplete="off">
    <button type="submit" class="ciocia-search-dialog__submit" aria-label="Szukaj">
      <i class="material-icons" aria-hidden="true">search</i>
    </button>
  </form>
</dialog>
