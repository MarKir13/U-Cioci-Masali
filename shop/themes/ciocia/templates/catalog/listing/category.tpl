{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * PrestaShop looks for catalog/listing/category in the child theme first, and only then in Classic. Our
 * product-list.tpl is a child theme template, so without this file Classic's category.tpl is never used
 * and the category header (title, description, subcategories) is not shown (issue #75).
 *}
{extends file='catalog/listing/product-list.tpl'}

{block name='product_list_header'}
  {include file='catalog/_partials/category-header.tpl' listing=$listing category=$category}
{/block}

{block name='product_list_footer'}
  {include file='catalog/_partials/category-footer.tpl' listing=$listing category=$category}
{/block}
