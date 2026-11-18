{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * The "added to cart" dialog of the source shop (issue #98): the title on the left with a green check,
 * the product and the cart totals in two columns without a divider, and both buttons in a row under them.
 * The layout uses its own .ciocia-added classes, so Classic's #blockcart-modal .cart-content rules do not
 * apply; styles in custom.css. ps_shoppingcart.js replaces the whole #blockcart-modal on every add, and the
 * E2E helper (tests/pages/catalog.js) relies on #blockcart-modal, .product-name and the dismiss button.
 *}
<div id="blockcart-modal" class="modal fade" tabindex="-1" role="dialog" aria-labelledby="myModalLabel" aria-hidden="true">
  <div class="modal-dialog" role="document">
    <div class="modal-content">
      <div class="modal-header">
        <h4 class="modal-title" id="myModalLabel"><i class="material-icons rtl-no-flip" aria-hidden="true">&#xE876;</i>Dodano do koszyka</h4>
        <button type="button" class="close" data-dismiss="modal" aria-label="{l s='Close' d='Shop.Theme.Global'}">
          <span aria-hidden="true"><i class="material-icons">close</i></span>
        </button>
      </div>
      <div class="modal-body">
        <div class="ciocia-added">
          <div class="ciocia-added__product">
            {if $product.default_image}
              <img
                src="{$product.default_image.medium.url}"
                alt="{$product.default_image.legend}"
                loading="lazy"
                class="product-image"
              >
            {else}
              <img
                src="{$urls.no_picture_image.bySize.medium_default.url}"
                alt=""
                loading="lazy"
                class="product-image"
              >
            {/if}
            <div class="ciocia-added__info">
              <p class="product-name">{$product.name}</p>
              <p class="product-price">{$product.price}</p>
              {hook h='displayProductPriceBlock' product=$product type="unit_price"}
              {foreach from=$product.attributes item="property_value" key="property"}
                <p class="{$property|lower}">{l s='%label%:' sprintf=['%label%' => $property] d='Shop.Theme.Global'} {$property_value}</p>
              {/foreach}
              <p class="product-quantity">{l s='Quantity:' d='Shop.Theme.Checkout'} {$product.cart_quantity}</p>
            </div>
          </div>

          <div class="ciocia-added__cart">
            {if $cart.products_count > 1}
              <p class="cart-products-count">{l s='There are %products_count% items in your cart.' sprintf=['%products_count%' => $cart.products_count] d='Shop.Theme.Checkout'}</p>
            {else}
              <p class="cart-products-count">{l s='There is %products_count% item in your cart.' sprintf=['%products_count%' => $cart.products_count] d='Shop.Theme.Checkout'}</p>
            {/if}
            <p class="ciocia-added__row"><span class="label">{l s='Subtotal:' d='Shop.Theme.Checkout'}</span><span class="subtotal value">{$cart.subtotals.products.value}</span></p>
            {if $cart.subtotals.shipping.value}
              <p class="ciocia-added__row"><span class="label">{l s='Shipping:' d='Shop.Theme.Checkout'}</span><span class="shipping value">{$cart.subtotals.shipping.value} {hook h='displayCheckoutSubtotalDetails' subtotal=$cart.subtotals.shipping}</span></p>
            {/if}

            {if !$configuration.display_prices_tax_incl && $configuration.taxes_enabled}
              <p class="ciocia-added__row"><span class="label">{$cart.totals.total.label}{if $configuration.display_taxes_label} {$cart.labels.tax_short}{/if}</span><span class="value">{$cart.totals.total.value}</span></p>
              <p class="ciocia-added__row product-total"><span class="label">{$cart.totals.total_including_tax.label}</span><span class="value">{$cart.totals.total_including_tax.value}</span></p>
            {else}
              <p class="ciocia-added__row product-total"><span class="label">{$cart.totals.total.label}{if $configuration.taxes_enabled && $configuration.display_taxes_label} {$cart.labels.tax_short}{/if}</span><span class="value">{$cart.totals.total.value}</span></p>
            {/if}

            {if $cart.subtotals.tax}
              <p class="ciocia-added__row product-tax"><span class="label">{l s='%label%:' sprintf=['%label%' => $cart.subtotals.tax.label] d='Shop.Theme.Global'}</span><span class="value">{$cart.subtotals.tax.value}</span></p>
            {/if}
            {hook h='displayCartModalContent' product=$product}
          </div>
        </div>

        <div class="ciocia-added__actions">
          <button type="button" class="btn btn-outline-primary" data-dismiss="modal">{l s='Continue shopping' d='Shop.Theme.Actions'}</button>
          <a href="{$cart_url}" class="btn btn-primary">Przejdź do kasy</a>
        </div>
      </div>
      {hook h='displayCartModalFooter' product=$product}
    </div>
  </div>
</div>
