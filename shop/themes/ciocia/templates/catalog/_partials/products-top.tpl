{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Above the products, as on the source (issue #75): "Liczba produktów: N" on the left and the sorting on
 * the right (on phones the sorting comes first), then the page links alone on the right.
 * There is no "Filtruj" button: the source has no filters, and the full-width layout has no column for
 * them (catalog/listing/product-list.tpl).
 *}
<div id="js-product-list-top" class="ciocia-products-top">
  <div class="ciocia-products-top__bar">
    <p class="ciocia-products-top__count">Liczba produktów: {$listing.pagination.total_items}</p>
    {block name='sort_by'}
      {include file='catalog/_partials/sort-orders.tpl' sort_orders=$listing.sort_orders}
    {/block}
  </div>

  {if $listing.pagination.should_be_displayed}
    {include file='_partials/pagination.tpl' pagination=$listing.pagination ciocia_position='top'}
  {/if}
</div>
