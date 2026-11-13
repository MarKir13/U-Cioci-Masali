{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Search results (issue #75): the list of catalog/listing/product-list.tpl. Only the message for no results
 * differs; Classic's is an h4 straight under the h1, which skips heading levels, so here it is an h2 that
 * looks the same.
 *}
{extends file='catalog/listing/product-list.tpl'}

{block name="error_content"}
  <h2 id="product-search-no-matches" class="h4">{l s='No matches were found for your search' d='Shop.Theme.Catalog'}</h2>
  <p>{l s='Please try other keywords to describe what you are looking for.' d='Shop.Theme.Catalog'}</p>
{/block}
