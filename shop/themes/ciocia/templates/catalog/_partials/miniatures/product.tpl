{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
{*
 * Classic's product card in lists (category, search, home page sections), plus the Omnibus line under
 * the price (module ciociaomnibus).
 *}
{extends file='parent:catalog/_partials/miniatures/product.tpl'}

{block name='product_price_and_shipping'}
  {$smarty.block.parent}
  {hook h='displayProductPriceBlock' product=$product type='omnibus_price'}
{/block}
