{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * .ciocia-cart-panel is the cart preview of the source shop. From 768 px it opens on hover and on
 * keyboard focus (CSS in custom.css; custom.js adds Escape); below 768 px it is not shown. It sits
 * inside .blockcart on purpose: after an AJAX refresh ps_shoppingcart replaces the whole .blockcart
 * with the one rendered from this template, so the panel always shows the current cart.
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
    <div class="ciocia-cart-panel">
      <div class="ciocia-cart-panel__box">
        {if $cart.products_count > 0}
          <ul class="ciocia-cart-panel__items">
            {foreach from=$cart.products item=product}
              <li class="ciocia-cart-panel__item">
                <div class="ciocia-cart-panel__info">
                  <a class="ciocia-cart-panel__name" href="{$product.url|escape:'htmlall':'UTF-8'}">{$product.cart_quantity} &times; {$product.name|escape:'htmlall':'UTF-8'}</a>
                  {foreach from=$product.attributes key=attribute item=value}
                    <span class="ciocia-cart-panel__attr">{$attribute|escape:'htmlall':'UTF-8'}: {$value|escape:'htmlall':'UTF-8'}</span>
                  {/foreach}
                  {* Same attributes as Classic's cart page, so core.js removes the line over AJAX and ps_shoppingcart refreshes this panel. *}
                  {if empty($product.is_gift)}
                    <a class="ciocia-cart-panel__remove remove-from-cart" rel="nofollow" href="{$product.remove_from_cart_url|escape:'htmlall':'UTF-8'}"
                       data-link-action="delete-from-cart" data-id-product="{$product.id_product|escape:'javascript'}"
                       data-id-product-attribute="{$product.id_product_attribute|escape:'javascript'}"
                       data-id-customization="{$product.id_customization|default:0|escape:'javascript'}">Usuń<span class="sr-only"> {$product.name|escape:'htmlall':'UTF-8'} z koszyka</span></a>
                  {/if}
                </div>
                <span class="ciocia-cart-panel__line">{$product.total}</span>
              </li>
            {/foreach}
          </ul>
          <dl class="ciocia-cart-panel__totals">
            <div><dt>Produkty</dt><dd>{$cart.subtotals.products.value}</dd></div>
            {if $cart.subtotals.shipping.value}
              <div><dt>Wysyłka</dt><dd>{$cart.subtotals.shipping.value}</dd></div>
            {/if}
            {if $cart.subtotals.tax && $cart.subtotals.tax.value}
              <div><dt>VAT (wliczony)</dt><dd>{$cart.subtotals.tax.value}</dd></div>
            {/if}
            <div class="ciocia-cart-panel__total"><dt>Razem</dt><dd>{$cart.totals.total.value}</dd></div>
          </dl>
        {else}
          <p class="ciocia-cart-panel__empty">Twój koszyk jest pusty</p>
        {/if}
      </div>
    </div>
  </div>
</div>
