{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * The products and the page links under them (issue #75). Classic's "Powrót do góry" button for phones
 * is left out, as on the source.
 *}
<div id="js-product-list">
  {include file="catalog/_partials/productlist.tpl" products=$listing.products}

  {block name='pagination'}
    {include file='_partials/pagination.tpl' pagination=$listing.pagination}
  {/block}
</div>
