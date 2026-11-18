{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Cart page product line laid out as on the source (issue #44): image; name, delivery time, price,
 * attributes and "Usuń"; on the right the quantity ("− 1 +") with the line total under it.
 * Kept for Classic's cart script (themes/classic/_dev/js/cart.js):
 * - the quantity field input[name="product-quantity-spin"] with its data-*-url attributes; Classic turns
 *   it into a TouchSpin field, custom.css lays its buttons out as "− 1 +" and custom.js names them;
 * - the delete link with data-link-action="delete-from-cart";
 * - .product-line-actions around both: typing 0 clicks the delete link found through it.
 *}
<div class="product-line-grid product-line-actions ciocia-line">
  <div class="ciocia-line__image">
    <span class="product-image media-middle">
      {if $product.default_image}
        <picture>
          {if !empty($product.default_image.bySize.cart_default.sources.avif)}<source srcset="{$product.default_image.bySize.cart_default.sources.avif}" type="image/avif">{/if}
          {if !empty($product.default_image.bySize.cart_default.sources.webp)}<source srcset="{$product.default_image.bySize.cart_default.sources.webp}" type="image/webp">{/if}
          <img src="{$product.default_image.bySize.cart_default.url}" alt="{$product.name|escape:'quotes'}" loading="lazy">
        </picture>
      {else}
        <picture>
          {if !empty($urls.no_picture_image.bySize.cart_default.sources.avif)}<source srcset="{$urls.no_picture_image.bySize.cart_default.sources.avif}" type="image/avif">{/if}
          {if !empty($urls.no_picture_image.bySize.cart_default.sources.webp)}<source srcset="{$urls.no_picture_image.bySize.cart_default.sources.webp}" type="image/webp">{/if}
          <img src="{$urls.no_picture_image.bySize.cart_default.url}" alt="" loading="lazy">
        </picture>
      {/if}
    </span>
  </div>

  <div class="ciocia-line__body">
    <a class="ciocia-line__name" href="{$product.url}" data-id_customization="{$product.id_customization|intval}">{$product.name}</a>

    {* Delivery time from the configuration (shop-settings.php, delivery_time_available) while in stock. *}
    {if $product.delivery_information}
      <p class="ciocia-line__delivery">{$product.delivery_information}</p>
    {/if}

    <div class="product-line-info product-price {if $product.has_discount}has-discount{/if}">
      {if $product.has_discount}
        <div class="product-discount">
          <span class="regular-price">{$product.regular_price}</span>
          {if $product.discount_type === 'percentage'}
            <span class="discount discount-percentage">-{$product.discount_percentage_absolute}</span>
          {else}
            <span class="discount discount-amount">-{$product.discount_to_display}</span>
          {/if}
        </div>
      {/if}
      <div class="current-price">
        <span class="price">{$product.price}</span>
        {if $product.unit_price_full}
          <div class="unit-price-cart">{$product.unit_price_full}</div>
        {/if}
      </div>
      {hook h='displayProductPriceBlock' product=$product type="unit_price"}
    </div>

    {foreach from=$product.attributes key="attribute" item="value"}
      <div class="product-line-info ciocia-line__attribute {$attribute|lower}">
        <span class="label">{$attribute}:</span>
        <span class="value">{$value}</span>
      </div>
    {/foreach}

    {if is_array($product.customizations) && $product.customizations|count}
      {block name='cart_detailed_product_line_customization'}
        {foreach from=$product.customizations item="customization"}
          <a href="#" data-toggle="modal" data-target="#product-customizations-modal-{$customization.id_customization}">{l s='Product customization' d='Shop.Theme.Catalog'}</a>
          <div class="modal fade customization-modal js-customization-modal" id="product-customizations-modal-{$customization.id_customization}" tabindex="-1" role="dialog" aria-hidden="true">
            <div class="modal-dialog" role="document">
              <div class="modal-content">
                <div class="modal-header">
                  <button type="button" class="close" data-dismiss="modal" aria-label="{l s='Close' d='Shop.Theme.Global'}">
                    <span aria-hidden="true">&times;</span>
                  </button>
                  <h4 class="modal-title">{l s='Product customization' d='Shop.Theme.Catalog'}</h4>
                </div>
                <div class="modal-body">
                  {foreach from=$customization.fields item="field"}
                    <div class="product-customization-line row">
                      <div class="col-sm-3 col-xs-4 label">
                        {$field.label}
                      </div>
                      <div class="col-sm-9 col-xs-8 value">
                        {if $field.type == 'text'}
                          {if (int)$field.id_module}
                            {$field.text nofilter}
                          {else}
                            {$field.text}
                          {/if}
                        {elseif $field.type == 'image'}
                          <img src="{$field.image.small.url}" alt="" loading="lazy">
                        {/if}
                      </div>
                    </div>
                  {/foreach}
                </div>
              </div>
            </div>
          </div>
        {/foreach}
      {/block}
    {/if}

    <div class="cart-line-product-actions">
      {if empty($product.is_gift)}
        <a
          class="remove-from-cart ciocia-line__remove"
          rel="nofollow"
          href="{$product.remove_from_cart_url}"
          data-link-action="delete-from-cart"
          data-id-product="{$product.id_product|escape:'javascript'}"
          data-id-product-attribute="{$product.id_product_attribute|escape:'javascript'}"
          data-id-customization="{$product.id_customization|default|escape:'javascript'}"
        >Usuń<span class="sr-only"> {$product.name} z koszyka</span></a>
      {/if}

      {block name='hook_cart_extra_product_actions'}
        {hook h='displayCartExtraProductActions' product=$product}
      {/block}
    </div>
  </div>

  <div class="ciocia-line__actions">
    <div class="qty">
      {if !empty($product.is_gift)}
        <span class="gift-quantity">{$product.quantity}</span>
      {else}
        <input
          class="js-cart-line-product-quantity"
          data-down-url="{$product.down_quantity_url}"
          data-up-url="{$product.up_quantity_url}"
          data-update-url="{$product.update_quantity_url}"
          data-product-id="{$product.id_product}"
          data-label-down="Zmniejsz ilość: {$product.name}"
          data-label-up="Zwiększ ilość: {$product.name}"
          type="number"
          inputmode="numeric"
          pattern="[0-9]*"
          value="{$product.quantity}"
          name="product-quantity-spin"
          aria-label="{l s='%productName% product quantity field' sprintf=['%productName%' => $product.name] d='Shop.Theme.Checkout'}"
        />
      {/if}
    </div>
    <div class="ciocia-line__total product-price">
      <strong>
        {if !empty($product.is_gift)}
          <span class="gift">{l s='Gift' d='Shop.Theme.Checkout'}</span>
        {else}
          {$product.total}
        {/if}
      </strong>
    </div>
  </div>
</div>
