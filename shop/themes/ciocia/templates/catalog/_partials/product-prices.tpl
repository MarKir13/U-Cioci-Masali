{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
{* Classic's price block on the product page, plus the Omnibus line under the price (module ciociaomnibus). *}
{extends file='parent:catalog/_partials/product-prices.tpl'}

{* The unit price of the source ("100g = 12.37 zł"), calculated from the size in the product name by the module
   ciociaomnibus (type 'ciocia_unit_price'), in place of Classic's own line, which needs unity and a ratio per product. *}
{block name='product_unit_price'}
  {hook h='displayProductPriceBlock' product=$product type='ciocia_unit_price'}
{/block}

{block name='product_price'}
  {$smarty.block.parent}
  {hook h='displayProductPriceBlock' product=$product type='omnibus_price'}
{/block}
