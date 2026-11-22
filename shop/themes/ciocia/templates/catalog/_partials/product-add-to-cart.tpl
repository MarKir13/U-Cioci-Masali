{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
{* Classic's add to cart block with one change (issue #76): an unavailable product says "Obecnie brak na stanie",
   the wording of the source shop, whatever label PrestaShop has for it. Styled in custom.css (#product-availability). *}
{extends file='parent:catalog/_partials/product-add-to-cart.tpl'}

{block name='product_availability'}
  <span id="product-availability" class="js-product-availability">
    {if $product.show_availability && $product.availability_message}
      {if $product.availability == 'available'}
        <i class="material-icons rtl-no-flip product-available">&#xE5CA;</i>
        {$product.availability_message}
      {elseif $product.availability == 'last_remaining_items'}
        <i class="material-icons product-last-items">&#xE002;</i>
        {$product.availability_message}
      {else}
        <i class="material-icons product-unavailable">&#xE14B;</i>
        Obecnie brak na stanie
      {/if}
    {/if}
  </span>
{/block}
