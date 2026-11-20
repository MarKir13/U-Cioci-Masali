{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
{* Flags over the photo on the product page (issue #76). An unavailable product always gets the out_of_stock flag
   with the source shop's wording, drawn as a ribbon by custom.css (body#product .product-flags). "Nowy" is not
   shown here: the importer gives every product the date of the import, so Classic would mark all of them new. *}
{block name='product_flags'}
  {$ciocia_out_of_stock = $product.availability == 'unavailable'}
  <ul class="product-flags js-product-flags">
    {foreach from=$product.flags item=flag}
      {if $flag.type == 'out_of_stock'}
        {$ciocia_out_of_stock = true}
      {elseif $flag.type == 'discount' && $product.regular_price_amount > 0}
        {* The label of a promotion of a fixed amount would be "-11,61 zł"; the ribbon shows the percentage *}
        {$ciocia_percent = (($product.regular_price_amount - $product.price_amount) / $product.regular_price_amount * 100)|round:0}
        <li class="product-flag discount">-{$ciocia_percent}%</li>
      {elseif $flag.type != 'new'}
        <li class="product-flag {$flag.type}">{$flag.label}</li>
      {/if}
    {/foreach}
    {if $ciocia_out_of_stock}
      <li class="product-flag out_of_stock">Obecnie brak na stanie</li>
    {/if}
  </ul>
{/block}
