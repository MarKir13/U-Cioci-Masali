{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Checkout summary (issue #44): the product count in bold, and "Pokaż szczegóły" as a full-width row
 * that opens the product list, as on the source. A button instead of Classic's link to "#", so it is
 * announced as one; Bootstrap's collapse keeps its aria-expanded up to date, which turns the chevron.
 *}
<div class="cart-summary-products js-cart-summary-products">
  <p class="ciocia-summary-count">{$cart.summary_string}</p>
  <button type="button" class="ciocia-summary-toggle" data-toggle="collapse" data-target="#cart-summary-product-list"
          aria-expanded="false" aria-controls="cart-summary-product-list">
    Pokaż szczegóły
    <i class="material-icons" aria-hidden="true">expand_more</i>
  </button>

  {block name='cart_summary_product_list'}
    <div class="collapse" id="cart-summary-product-list">
      <ul class="media-list">
        {foreach from=$cart.products item=product}
          <li class="media">{include file='checkout/_partials/cart-summary-product-line.tpl' product=$product}</li>
        {/foreach}
      </ul>
    </div>
  {/block}
</div>
