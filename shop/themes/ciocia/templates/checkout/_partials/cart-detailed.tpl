{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Cart list, then "Kontynuuj zakupy", then the info box (cart-info.tpl), in the order of the source
 * (issue #44). All three sit inside .cart-overview: Classic replaces that element with this template
 * after every cart change, so the box stays current; outside it, every refresh would add a copy.
 * The link takes the place of Classic's continue_shopping block in cart.tpl, which is left empty.
 *}
{block name='cart_detailed_product'}
  <div class="cart-overview js-cart" data-refresh-url="{url entity='cart' params=['ajax' => true, 'action' => 'refresh']}">
    {if $cart.products}
    <ul class="cart-items">
      {foreach from=$cart.products item=product}
        <li class="cart-item">
          {block name='cart_detailed_product_line'}
            {include file='checkout/_partials/cart-detailed-product-line.tpl' product=$product}
          {/block}
        </li>
        {if is_array($product.customizations) && $product.customizations|count >1}<hr>{/if}
      {/foreach}
    </ul>
    {include file='checkout/_partials/continue-shopping.tpl'}
    {include file='checkout/_partials/cart-info.tpl'}
    {else}
      <span class="no-items">{l s='There are no more items in your cart' d='Shop.Theme.Checkout'}</span>
      {include file='checkout/_partials/continue-shopping.tpl'}
    {/if}
  </div>
{/block}
