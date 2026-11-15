{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Supplier page: Classic's header (name and description) in our listing header, without Classic's
 * product_list block (our product-list.tpl already renders the grid), as manufacturer.tpl (issue #75).
 *}
{extends file='catalog/listing/product-list.tpl'}

{block name='product_list_header'}
  <div id="js-product-list-header" class="ciocia-listing__header">
    <h1 class="ciocia-listing__title">{l s='List of products by supplier %s' sprintf=[$supplier.name] d='Shop.Theme.Catalog'}</h1>
    <div id="supplier-description">{$supplier.description nofilter}</div>
  </div>
{/block}
