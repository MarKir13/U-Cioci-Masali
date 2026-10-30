{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
<div id="_desktop_cart">
  <div class="blockcart cart-preview {if $cart.products_count > 0}active{else}inactive{/if}" data-refresh-url="{$refresh_url|escape:'htmlall':'UTF-8'}">
    <div class="header">
      <a class="ciocia-cart-link" rel="nofollow" href="{$cart_url|escape:'htmlall':'UTF-8'}">
        <span class="ciocia-cart-icon" aria-hidden="true">
          <i class="material-icons shopping-cart">shopping_cart</i>
          <span class="ciocia-cart-badge">{$cart.products_count}</span>
        </span>
        <span class="sr-only hidden-md-up">Koszyk ({$cart.products_count})</span>
        <span class="ciocia-cart-copy">
          <span class="ciocia-cart-title">{l s='Cart' d='Shop.Theme.Checkout'} <span class="cart-products-count">({$cart.products_count})</span></span>
          <span class="ciocia-cart-subtitle">Zobacz koszyk</span>
        </span>
      </a>
    </div>
  </div>
</div>
