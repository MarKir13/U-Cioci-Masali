{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Brand page: Classic's header (name and descriptions) in our listing header, without Classic's product_list
 * block (our product-list.tpl already renders the grid). Needed because the child theme's product-list.tpl
 * is found before Classic's manufacturer.tpl is used (issue #75).
 *}
{extends file='catalog/listing/product-list.tpl'}

{block name='product_list_header'}
  <div id="js-product-list-header" class="ciocia-listing__header">
    <h1 class="ciocia-listing__title">{l s='List of products by brand %brand_name%' sprintf=['%brand_name%' => $manufacturer.name] d='Shop.Theme.Catalog'}</h1>
    <div id="manufacturer-short_description">{$manufacturer.short_description nofilter}</div>
    <div id="manufacturer-description">{$manufacturer.description nofilter}</div>
  </div>
{/block}
