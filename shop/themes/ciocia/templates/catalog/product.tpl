{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
{* Classic's product page, plus the product's family (module ciociafamily, issue #114): the rows of sibling tiles,
   right under the photo and the buying column. custom.js then puts the description after them, as on the source. *}
{extends file='parent:catalog/product.tpl'}

{block name='product_accessories'}
  {hook h='displayCiociaProductFamily' product=$product}
  {$smarty.block.parent}
{/block}
